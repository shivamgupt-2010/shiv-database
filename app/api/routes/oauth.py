import os
import json
import base64
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode, quote, unquote

from fastapi import APIRouter, Depends, Request, Form, Query, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
import jwt

from app.core.config import settings
from app.database.session import get_db_session as get_db
from app.database.models.auth import User
from app.database.models.oauth import (
    OAuthClient,
    OAuthAuthorizationCode,
    OAuthConsentGrant,
    OAuthToken,
)
from app.auth.keys import key_manager
from app.auth.tokens import create_access_token, verify_access_token
from app.auth.password import verify_password
from app.api.dependencies import get_auth_service, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["OAuth 2.0 & OpenID Connect"])

templates = Jinja2Templates(directory="app/templates")

SCOPE_METADATA = {
    "openid": {
        "title": "Basic Identity",
        "description": "Verify your identity and unique SHIV ID.",
        "icon": "🆔"
    },
    "profile": {
        "title": "Account Profile",
        "description": "View your username, display name, and avatar picture.",
        "icon": "👤"
    },
    "email": {
        "title": "Email Address",
        "description": "View your email address and verification status.",
        "icon": "✉️"
    },
    "offline_access": {
        "title": "Offline / Persistent Access",
        "description": "Maintain access when you are not actively using the application.",
        "icon": "🔄"
    }
}


def get_issuer_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    proto = request.headers.get("x-forwarded-proto", "")
    if "https" in proto and base.startswith("http://"):
        base = "https://" + base[7:]
    return base


def validate_redirect_uri(client: OAuthClient, redirect_uri: str) -> bool:
    try:
        registered_uris = json.loads(client.redirect_uris_json)
    except Exception:
        registered_uris = []
    # Strict exact string matching as required by RFC 6749 & OAuth 2.1
    return redirect_uri in registered_uris


async def get_user_from_request_or_token(request: Request, db: AsyncSession) -> Optional[User]:
    """Inspects Authorization header, cookie, or query param to find active session."""
    auth_header = request.headers.get("Authorization")
    token_str = None
    if auth_header and auth_header.startswith("Bearer "):
        token_str = auth_header[7:].strip()
    if not token_str:
        token_str = request.cookies.get("shiv_session_token") or request.query_params.get("session_token")

    if not token_str:
        return None

    try:
        payload = verify_access_token(token_str)
        user_id = payload.get("sub")
        if not user_id:
            return None
        stmt = select(User).where(User.id == user_id, User.status == "active")
        res = await db.execute(stmt)
        return res.scalar_one_or_none()
    except Exception:
        return None


@router.get("/authorize")
async def authorize(
    request: Request,
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query("code"),
    scope: str = Query("openid"),
    state: Optional[str] = Query(None),
    code_challenge: Optional[str] = Query(None),
    code_challenge_method: Optional[str] = Query(None),
    nonce: Optional[str] = Query(None),
    prompt: Optional[str] = Query(None),
    session_token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth 2.0 / OpenID Connect Authorization Endpoint.
    Validates request parameters, handles user consent, and redirects with authorization code.
    """
    # 1. Validate Client
    stmt = select(OAuthClient).where(OAuthClient.client_id == client_id)
    res = await db.execute(stmt)
    client = res.scalar_one_or_none()
    if not client or client.status != "active":
        raise HTTPException(status_code=400, detail="Invalid, revoked, or suspended client_id")

    # 2. Strict exact redirect_uri validation
    if not validate_redirect_uri(client, redirect_uri):
        logger.warning(f"Redirect URI mismatch for {client_id}: {redirect_uri}")
        raise HTTPException(status_code=400, detail="Invalid redirect_uri for this application")

    # 3. Response type must be code
    if response_type != "code":
        return RedirectResponse(
            f"{redirect_uri}?error=unsupported_response_type&error_description=Only+response_type=code+is+supported&state={state or ''}"
        )

    # 4. PKCE validation: public clients MUST supply code_challenge with S256
    if client.client_type == "public" and not code_challenge:
        return RedirectResponse(
            f"{redirect_uri}?error=invalid_request&error_description=PKCE+code_challenge+is+required+for+public+clients&state={state or ''}"
        )

    if code_challenge and code_challenge_method != "S256":
        return RedirectResponse(
            f"{redirect_uri}?error=invalid_request&error_description=Only+code_challenge_method=S256+is+supported&state={state or ''}"
        )

    # 5. Check if user is authenticated
    user = await get_user_from_request_or_token(request, db)
    if not user:
        # User not logged in, redirect to login page with return_to
        login_url = f"/dashboard?return_to={quote(str(request.url))}"
        return RedirectResponse(login_url)

    # 6. Check existing user consent grant
    scopes_requested = scope.strip().split()
    stmt_grant = select(OAuthConsentGrant).where(
        OAuthConsentGrant.user_id == user.id,
        OAuthConsentGrant.client_id == client.client_id,
        OAuthConsentGrant.revoked == False
    )
    res_grant = await db.execute(stmt_grant)
    existing_grant = res_grant.scalar_one_or_none()

    has_all_scopes = False
    if existing_grant and prompt != "consent":
        granted_set = set(existing_grant.granted_scopes.split())
        if set(scopes_requested).issubset(granted_set):
            has_all_scopes = True

    if has_all_scopes:
        # Issue code immediately without re-prompting consent
        raw_code = f"shiv_ac_{secrets.token_urlsafe(32)}"
        code_hash = hashlib.sha256(raw_code.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        auth_code_record = OAuthAuthorizationCode(
            code_hash=code_hash,
            client_id=client.client_id,
            user_id=user.id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            nonce=nonce,
            expires_at=expires_at,
            used=False
        )
        db.add(auth_code_record)
        await db.commit()

        delim = "&" if "?" in redirect_uri else "?"
        params = {"code": raw_code}
        if state:
            params["state"] = state
        return RedirectResponse(f"{redirect_uri}{delim}{urlencode(params)}")

    # 7. Render Consent Screen
    scopes_list = []
    for s in scopes_requested:
        meta = SCOPE_METADATA.get(s, {"title": s.capitalize(), "description": f"Access to {s} scope.", "icon": "🔒"})
        scopes_list.append(meta)

    # Create signed consent token preventing tampering
    consent_payload = {
        "sub": user.id,
        "client_id": client.client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
    }
    consent_token, _ = create_access_token(consent_payload)

    return templates.TemplateResponse(
        request=request,
        name="consent.html",
        context={
            "client_name": client.client_name,
            "logo_uri": client.logo_uri,
            "user_display_name": user.display_name or user.username,
            "user_shiv_id": user.shiv_id or "SHV-USER",
            "client_id": client.client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state or "",
            "code_challenge": code_challenge or "",
            "code_challenge_method": code_challenge_method or "",
            "nonce": nonce or "",
            "consent_token": consent_token,
            "scopes_list": scopes_list
        }
    )


@router.post("/authorize/consent")
async def authorize_consent(
    request: Request,
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    scope: str = Form(...),
    state: Optional[str] = Form(None),
    code_challenge: Optional[str] = Form(None),
    code_challenge_method: Optional[str] = Form(None),
    nonce: Optional[str] = Form(None),
    consent_token: str = Form(...),
    action: str = Form("approve"),
    db: AsyncSession = Depends(get_db)
):
    """Handles User Consent approval or denial."""
    # If user denied:
    if action != "approve":
        delim = "&" if "?" in redirect_uri else "?"
        params = {"error": "access_denied", "error_description": "User denied the authorization request"}
        if state:
            params["state"] = state
        return RedirectResponse(f"{redirect_uri}{delim}{urlencode(params)}", status_code=303)

    # Validate consent token
    try:
        payload = verify_access_token(consent_token)
        user_id = payload.get("sub")
        if payload.get("client_id") != client_id or payload.get("redirect_uri") != redirect_uri:
            raise HTTPException(status_code=400, detail="Invalid consent token binding")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Consent validation failed: {str(e)}")

    # Record or update consent grant
    stmt_grant = select(OAuthConsentGrant).where(
        OAuthConsentGrant.user_id == user_id,
        OAuthConsentGrant.client_id == client_id
    )
    res_grant = await db.execute(stmt_grant)
    grant = res_grant.scalar_one_or_none()
    if grant:
        grant.granted_scopes = scope
        grant.revoked = False
    else:
        grant = OAuthConsentGrant(
            user_id=user_id,
            client_id=client_id,
            granted_scopes=scope,
            revoked=False
        )
        db.add(grant)

    # Issue single-use Authorization Code
    raw_code = f"shiv_ac_{secrets.token_urlsafe(32)}"
    code_hash = hashlib.sha256(raw_code.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    auth_code_record = OAuthAuthorizationCode(
        code_hash=code_hash,
        client_id=client_id,
        user_id=user_id,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge=code_challenge if code_challenge else None,
        code_challenge_method=code_challenge_method if code_challenge_method else None,
        nonce=nonce if nonce else None,
        expires_at=expires_at,
        used=False
    )
    db.add(auth_code_record)
    await db.commit()

    delim = "&" if "?" in redirect_uri else "?"
    params = {"code": raw_code}
    if state:
        params["state"] = state

    return RedirectResponse(f"{redirect_uri}{delim}{urlencode(params)}", status_code=303)


@router.post("/token")
async def token(
    request: Request,
    grant_type: str = Form(...),
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    code_verifier: Optional[str] = Form(None),
    refresh_token: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth 2.0 / OpenID Connect Token Endpoint (RFC 6749 Section 4.1.3).
    Exchanges authorization code with PKCE verification for Access Token and RS256-signed ID Token.
    """
    # Check for HTTP Basic Auth header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Basic "):
        try:
            b64_creds = auth_header[6:].strip()
            decoded = base64.b64decode(b64_creds).decode("utf-8")
            if ":" in decoded:
                h_client_id, h_client_secret = decoded.split(":", 1)
                client_id = client_id or h_client_id
                client_secret = client_secret or h_client_secret
        except Exception:
            pass

    if not client_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_client", "error_description": "client_id is required"}
        )

    # Fetch Client
    stmt = select(OAuthClient).where(OAuthClient.client_id == client_id)
    res = await db.execute(stmt)
    client = res.scalar_one_or_none()
    if not client or client.status != "active":
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_client", "error_description": "Client authentication failed"}
        )

    # Authenticate Confidential Client
    if client.client_type == "confidential":
        if not client_secret or not client.client_secret_hash:
            raise HTTPException(
                status_code=401,
                detail={"error": "invalid_client", "error_description": "Client secret required for confidential clients"}
            )
        sec_hash = hashlib.sha256(client_secret.encode()).hexdigest()
        if not secrets.compare_digest(sec_hash, client.client_secret_hash):
            raise HTTPException(
                status_code=401,
                detail={"error": "invalid_client", "error_description": "Invalid client secret"}
            )

    # ── GRANT TYPE: authorization_code ─────────────────────────────────────────
    if grant_type == "authorization_code":
        if not code:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_request", "error_description": "code is required"}
            )

        code_hash = hashlib.sha256(code.encode()).hexdigest()
        stmt_code = select(OAuthAuthorizationCode).where(OAuthAuthorizationCode.code_hash == code_hash)
        res_code = await db.execute(stmt_code)
        auth_code = res_code.scalar_one_or_none()

        if not auth_code:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_grant", "error_description": "Authorization code not found"}
            )

        # Single-use code check
        if auth_code.used:
            logger.warning(f"Replay attack detected for authorization code {code[:8]}...")
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_grant", "error_description": "Authorization code has already been used"}
            )

        # Immediately mark used
        auth_code.used = True
        await db.commit()

        # Expiry check
        if auth_code.is_expired:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_grant", "error_description": "Authorization code has expired"}
            )

        # Client mismatch check
        if auth_code.client_id != client.client_id:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_grant", "error_description": "Code was issued to a different client"}
            )

        # Redirect URI match check
        if redirect_uri and auth_code.redirect_uri != redirect_uri:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_grant", "error_description": "redirect_uri mismatch"}
            )

        # PKCE Verification
        if auth_code.code_challenge:
            if not code_verifier:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "invalid_grant", "error_description": "code_verifier required for PKCE"}
                )
            if auth_code.code_challenge_method == "S256":
                computed = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
                if not secrets.compare_digest(computed, auth_code.code_challenge):
                    raise HTTPException(
                        status_code=400,
                        detail={"error": "invalid_grant", "error_description": "PKCE verification failed"}
                    )
            elif auth_code.code_challenge_method == "plain":
                if not secrets.compare_digest(code_verifier, auth_code.code_challenge):
                    raise HTTPException(
                        status_code=400,
                        detail={"error": "invalid_grant", "error_description": "PKCE verification failed"}
                    )

        # Retrieve User
        stmt_user = select(User).where(User.id == auth_code.user_id)
        res_user = await db.execute(stmt_user)
        user = res_user.scalar_one_or_none()
        if not user or user.status != "active":
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_grant", "error_description": "User is inactive or not found"}
            )

        issuer = get_issuer_url(request)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        scopes_list = auth_code.scope.split()

        # 1. Access Token
        access_token_payload = {
            "iss": issuer,
            "sub": user.id,
            "client_id": client.client_id,
            "scope": auth_code.scope,
            "iat": now_ts,
            "exp": now_ts + 3600
        }
        access_token, _ = create_access_token(access_token_payload)

        # 2. RS256-signed OpenID Connect ID Token
        id_token_payload = {
            "iss": issuer,
            "sub": user.id,  # Immutable stable primary key
            "aud": client.client_id,
            "iat": now_ts,
            "exp": now_ts + 3600,
            "preferred_username": user.username,
            "shiv_id": user.shiv_id or "",
        }
        if auth_code.nonce:
            id_token_payload["nonce"] = auth_code.nonce

        if "profile" in scopes_list:
            id_token_payload["name"] = user.display_name or user.username
            if user.avatar_url:
                id_token_payload["picture"] = user.avatar_url

        if "email" in scopes_list:
            id_token_payload["email"] = user.email
            id_token_payload["email_verified"] = user.email_verified

        id_token = key_manager.sign_id_token(id_token_payload)

        resp_data = {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": id_token,
            "scope": auth_code.scope
        }

        # Issue Refresh Token if offline_access is requested
        if "offline_access" in scopes_list:
            raw_rf = f"shiv_rf_{secrets.token_urlsafe(48)}"
            rf_hash = hashlib.sha256(raw_rf.encode()).hexdigest()
            rf_token = OAuthToken(
                token_hash=rf_hash,
                token_type="refresh_token",
                client_id=client.client_id,
                user_id=user.id,
                scope=auth_code.scope,
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                revoked=False
            )
            db.add(rf_token)
            await db.commit()
            resp_data["refresh_token"] = raw_rf

        return JSONResponse(
            content=resp_data,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"}
        )

    # ── GRANT TYPE: refresh_token ──────────────────────────────────────────────
    elif grant_type == "refresh_token":
        if not refresh_token:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_request", "error_description": "refresh_token is required"}
            )

        rf_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        stmt_rf = select(OAuthToken).where(
            OAuthToken.token_hash == rf_hash,
            OAuthToken.token_type == "refresh_token",
            OAuthToken.client_id == client.client_id,
            OAuthToken.revoked == False
        )
        res_rf = await db.execute(stmt_rf)
        stored_rf = res_rf.scalar_one_or_none()
        if not stored_rf:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_grant", "error_description": "Invalid or expired refresh token"}
            )

        exp = stored_rf.expires_at
        now = datetime.now(timezone.utc) if exp.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
        if exp < now:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_grant", "error_description": "Invalid or expired refresh token"}
            )

        # Rotate refresh token (revoke old one)
        stored_rf.revoked = True

        stmt_user = select(User).where(User.id == stored_rf.user_id, User.status == "active")
        res_user = await db.execute(stmt_user)
        user = res_user.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=400, detail={"error": "invalid_grant", "error_description": "User inactive"})

        issuer = get_issuer_url(request)
        now_ts = int(datetime.now(timezone.utc).timestamp())

        # New Access Token
        access_token_payload = {
            "iss": issuer,
            "sub": user.id,
            "client_id": client.client_id,
            "scope": stored_rf.scope,
            "iat": now_ts,
            "exp": now_ts + 3600
        }
        access_token, _ = create_access_token(access_token_payload)

        # New Refresh Token
        new_raw_rf = f"shiv_rf_{secrets.token_urlsafe(48)}"
        new_rf_hash = hashlib.sha256(new_raw_rf.encode()).hexdigest()
        new_rf_record = OAuthToken(
            token_hash=new_rf_hash,
            token_type="refresh_token",
            client_id=client.client_id,
            user_id=user.id,
            scope=stored_rf.scope,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            revoked=False
        )
        db.add(new_rf_record)
        await db.commit()

        return JSONResponse(
            content={
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": new_raw_rf,
                "scope": stored_rf.scope
            },
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"}
        )

    else:
        raise HTTPException(
            status_code=400,
            detail={"error": "unsupported_grant_type", "error_description": f"Unsupported grant_type '{grant_type}'"}
        )


@router.get("/userinfo")
@router.post("/userinfo")
async def userinfo(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    OpenID Connect UserInfo Endpoint.
    Returns authenticated user claims filtered strictly by authorized scopes.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "error_description": "Bearer token required"}
        )

    token_str = auth_header[7:].strip()
    try:
        payload = verify_access_token(token_str)
        user_id = payload.get("sub")
        scope_str = payload.get("scope", "openid")
        scopes = scope_str.split()
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "error_description": str(e)}
        )

    stmt = select(User).where(User.id == user_id, User.status == "active")
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_token", "error_description": "User not found"}
        )

    claims = {
        "sub": user.id,  # Immutable stable primary key
        "preferred_username": user.username,
        "shiv_id": user.shiv_id or "",
    }

    if "profile" in scopes:
        claims["name"] = user.display_name or user.username
        if user.avatar_url:
            claims["picture"] = user.avatar_url
        if getattr(user, "bio", None):
            claims["bio"] = user.bio
        if getattr(user, "website", None):
            claims["website"] = user.website

    if "email" in scopes:
        claims["email"] = user.email
        claims["email_verified"] = user.email_verified

    return JSONResponse(content=claims)


@router.post("/revoke")
async def revoke(
    token: str = Form(...),
    token_type_hint: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """RFC 7009 Token Revocation endpoint."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = update(OAuthToken).where(OAuthToken.token_hash == token_hash).values(revoked=True)
    await db.execute(stmt)
    await db.commit()
    # RFC 7009 specifies returning HTTP 200 even if token was already revoked or not found
    return JSONResponse(content={"status": "revoked"})


@router.post("/introspect")
async def introspect(
    token: str = Form(...),
    token_type_hint: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """RFC 7662 Token Introspection endpoint."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = select(OAuthToken).where(OAuthToken.token_hash == token_hash)
    res = await db.execute(stmt)
    t = res.scalar_one_or_none()

    if not t or not t.is_active:
        return JSONResponse(content={"active": False})

    return JSONResponse(content={
        "active": True,
        "scope": t.scope,
        "client_id": t.client_id,
        "sub": t.user_id,
        "token_type": t.token_type,
        "exp": int(t.expires_at.timestamp())
    })


@router.get("/logout")
async def logout(
    request: Request,
    id_token_hint: Optional[str] = Query(None),
    post_logout_redirect_uri: Optional[str] = Query(None),
    state: Optional[str] = Query(None)
):
    """OpenID Connect RP-Initiated Logout."""
    response = RedirectResponse(post_logout_redirect_uri or "/dashboard")
    response.delete_cookie("shiv_session_token")
    return response


@router.get("/grants")
async def list_user_grants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List connected third-party applications for current user."""
    stmt = (
        select(OAuthConsentGrant, OAuthClient)
        .join(OAuthClient, OAuthClient.client_id == OAuthConsentGrant.client_id)
        .where(OAuthConsentGrant.user_id == current_user.id, OAuthConsentGrant.revoked == False)
    )
    res = await db.execute(stmt)
    rows = res.all()

    grants = []
    for grant, client in rows:
        grants.append({
            "client_id": client.client_id,
            "client_name": client.client_name,
            "logo_uri": client.logo_uri,
            "scopes": grant.granted_scopes,
            "granted_at": grant.created_at.isoformat() if grant.created_at else None
        })
    return JSONResponse(content={"success": True, "data": grants})


@router.delete("/grants/{client_id}")
async def revoke_user_grant(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke user consent grant for a third-party application."""
    stmt = (
        update(OAuthConsentGrant)
        .where(OAuthConsentGrant.user_id == current_user.id, OAuthConsentGrant.client_id == client_id)
        .values(revoked=True)
    )
    await db.execute(stmt)

    # Also revoke any issued tokens for this user and client
    stmt_tokens = (
        update(OAuthToken)
        .where(OAuthToken.user_id == current_user.id, OAuthToken.client_id == client_id)
        .values(revoked=True)
    )
    await db.execute(stmt_tokens)
    await db.commit()

    return JSONResponse(content={"success": True, "message": "Application access revoked"})
