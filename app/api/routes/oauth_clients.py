import json
import secrets
import hashlib
from typing import List, Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.core.config import settings
from app.database.session import get_db_session as get_db
from app.database.schemas.common import SuccessResponse
from app.database.models.auth import User
from app.database.models.oauth import OAuthClient
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/oauth/clients", tags=["OAuth Application Management"])


class ClientRegisterRequest(BaseModel):
    client_name: str = Field(min_length=2, max_length=150)
    client_type: str = Field(default="confidential", pattern=r"^(confidential|public)$")
    redirect_uris: List[str] = Field(min_length=1)
    client_uri: Optional[str] = None
    logo_uri: Optional[str] = None
    description: Optional[str] = None
    allowed_scopes: Optional[str] = "openid profile email"


class ClientUpdateRequest(BaseModel):
    client_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    redirect_uris: Optional[List[str]] = None
    client_uri: Optional[str] = None
    logo_uri: Optional[str] = None
    description: Optional[str] = None


def validate_uris(uris: List[str]):
    for uri in uris:
        parsed = urlparse(uri)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail=f"Invalid redirect URI: {uri}")
        if parsed.fragment:
            raise HTTPException(status_code=400, detail=f"Redirect URI cannot contain fragment identifier (#): {uri}")
        if "*" in uri:
            raise HTTPException(status_code=400, detail=f"Wildcards are forbidden in redirect URIs: {uri}")

        # Enforce HTTPS in non-local environments
        is_local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if not is_local and parsed.scheme != "https":
            if settings.ENVIRONMENT != "development":
                raise HTTPException(status_code=400, detail=f"Redirect URI must use HTTPS: {uri}")


@router.post("", response_model=SuccessResponse)
async def register_client(
    body: ClientRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Registers an external or internal OAuth 2.0 / OIDC client application.
    Generates unique client_id and hashed client_secret (for confidential clients).
    """
    validate_uris(body.redirect_uris)

    client_id = f"shiv_client_{secrets.token_hex(12)}"
    raw_secret = None
    secret_hash = None

    if body.client_type == "confidential":
        raw_secret = f"shiv_sec_{secrets.token_urlsafe(32)}"
        secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

    client = OAuthClient(
        client_id=client_id,
        client_secret_hash=secret_hash,
        client_name=body.client_name.strip(),
        client_uri=body.client_uri.strip() if body.client_uri else None,
        logo_uri=body.logo_uri.strip() if body.logo_uri else None,
        description=body.description.strip() if body.description else None,
        redirect_uris_json=json.dumps(body.redirect_uris),
        allowed_scopes=body.allowed_scopes.strip(),
        client_type=body.client_type,
        owner_user_id=current_user.id,
        status="active"
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    resp_data = {
        "client_id": client.client_id,
        "client_name": client.client_name,
        "client_type": client.client_type,
        "redirect_uris": body.redirect_uris,
        "allowed_scopes": client.allowed_scopes,
        "status": client.status,
        "created_at": client.created_at.isoformat() if client.created_at else None,
    }
    if raw_secret:
        resp_data["client_secret"] = raw_secret  # Returned ONLY ONCE upon creation!

    return SuccessResponse(data=resp_data, message="OAuth Application registered successfully")


@router.get("", response_model=SuccessResponse)
async def list_clients(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists all OAuth applications owned by the authenticated developer."""
    stmt = select(OAuthClient).where(OAuthClient.owner_user_id == current_user.id).order_by(OAuthClient.created_at.desc())
    res = await db.execute(stmt)
    clients = res.scalars().all()

    data = []
    for c in clients:
        try:
            uris = json.loads(c.redirect_uris_json)
        except Exception:
            uris = []
        data.append({
            "client_id": c.client_id,
            "client_name": c.client_name,
            "client_type": c.client_type,
            "client_uri": c.client_uri,
            "logo_uri": c.logo_uri,
            "description": c.description,
            "redirect_uris": uris,
            "allowed_scopes": c.allowed_scopes,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return SuccessResponse(data=data)


@router.get("/{client_id}", response_model=SuccessResponse)
async def get_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(OAuthClient).where(OAuthClient.client_id == client_id, OAuthClient.owner_user_id == current_user.id)
    res = await db.execute(stmt)
    c = res.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Application not found")

    try:
        uris = json.loads(c.redirect_uris_json)
    except Exception:
        uris = []

    return SuccessResponse(data={
        "client_id": c.client_id,
        "client_name": c.client_name,
        "client_type": c.client_type,
        "client_uri": c.client_uri,
        "logo_uri": c.logo_uri,
        "description": c.description,
        "redirect_uris": uris,
        "allowed_scopes": c.allowed_scopes,
        "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    })


@router.post("/{client_id}/rotate-secret", response_model=SuccessResponse)
async def rotate_secret(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Rotates client secret for confidential clients."""
    stmt = select(OAuthClient).where(OAuthClient.client_id == client_id, OAuthClient.owner_user_id == current_user.id)
    res = await db.execute(stmt)
    client = res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Application not found")
    if client.client_type != "confidential":
        raise HTTPException(status_code=400, detail="Public clients do not have client secrets")

    new_secret = f"shiv_sec_{secrets.token_urlsafe(32)}"
    client.client_secret_hash = hashlib.sha256(new_secret.encode()).hexdigest()
    await db.commit()

    return SuccessResponse(
        data={"client_id": client.client_id, "new_client_secret": new_secret},
        message="Client secret rotated successfully. Save this secret immediately."
    )


@router.delete("/{client_id}", response_model=SuccessResponse)
async def delete_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Deletes/revokes an OAuth application and its active tokens."""
    stmt = select(OAuthClient).where(OAuthClient.client_id == client_id, OAuthClient.owner_user_id == current_user.id)
    res = await db.execute(stmt)
    client = res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Application not found")

    await db.delete(client)
    await db.commit()
    return SuccessResponse(data={"client_id": client_id}, message="Application deleted successfully")
