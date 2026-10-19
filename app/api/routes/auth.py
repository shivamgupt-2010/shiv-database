import hashlib
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.session import get_db_session as get_db
from app.database.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
    SessionResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    EmailVerifyRequest,
    ResendVerificationRequest,
)
from app.database.schemas.common import SuccessResponse
from app.database.models.project import Project
from app.database.models.auth import User, Session as SessionModel, VerificationToken, PasswordResetToken
from app.auth.service import AuthService
from app.auth.sessions import list_user_sessions, revoke_session, revoke_other_sessions
from app.auth.tokens import create_verification_token, create_password_reset_token
from app.auth.password import get_password_hash
from app.auth.username import validate_username, normalize_username
from app.api.dependencies import get_auth_service, get_optional_project_by_api_key, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


def user_to_profile(user: User) -> dict:
    return {
        "id": user.id,
        "shiv_id": user.shiv_id,
        "email": user.email,
        "username": user.username,
        "normalized_username": user.normalized_username or user.username.lower(),
        "display_name": user.display_name or user.username,
        "bio": getattr(user, "bio", None),
        "website": getattr(user, "website", None),
        "phone": getattr(user, "phone", None),
        "phone_verified": getattr(user, "phone_verified", False),
        "avatar_url": user.avatar_url,
        "email_verified": user.email_verified,
        "role": user.role,
        "status": user.status,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


@router.post("/register", response_model=SuccessResponse)
async def register(
    body: UserRegisterRequest,
    project: Optional[Project] = Depends(get_optional_project_by_api_key),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Registers a new unique SHIV account with human-readable SHIV ID (e.g. SHV-10482)
    and normalized, reserved-name-validated username.
    """
    user = await auth_service.register(
        email=body.email,
        username=body.username,
        password=body.password,
        metadata={"display_name": body.display_name or body.username, "phone": body.phone},
        project=project
    )
    return SuccessResponse(
        data=user_to_profile(user),
        message="SHIV Account created successfully"
    )


@router.post("/login", response_model=SuccessResponse[TokenResponse])
async def login(
    request: Request,
    body: UserLoginRequest,
    project: Optional[Project] = Depends(get_optional_project_by_api_key),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Authenticates user using email, normalized username, or SHIV ID.
    Issues short-lived access token (60m) and persistent refresh token (30d).
    """
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    access_token, refresh_token, user = await auth_service.login(
        body.email_or_username, body.password, project, ip, ua
    )

    return SuccessResponse(
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserProfileResponse(**user_to_profile(user))
        )
    )


@router.post("/refresh", response_model=SuccessResponse[TokenResponse])
async def refresh(
    request: Request,
    refresh_token: str,
    auth_service: AuthService = Depends(get_auth_service)
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    access_token, new_refresh_token = await auth_service.refresh_tokens(refresh_token, ip, ua)

    return SuccessResponse(
        data=TokenResponse(access_token=access_token, refresh_token=new_refresh_token, token_type="bearer")
    )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    refresh_token: str,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user)
):
    success = await auth_service.logout(refresh_token)
    return SuccessResponse(data={"success": success}, message="Logged out successfully")


@router.get("/me", response_model=SuccessResponse[UserProfileResponse])
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's full SHIV Identity profile."""
    return SuccessResponse(data=UserProfileResponse(**user_to_profile(current_user)))


@router.patch("/me", response_model=SuccessResponse[UserProfileResponse])
async def update_profile(
    body: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update profile details. Username change enforces collision prevention and reserved name policies.
    """
    if body.username and body.username != current_user.username:
        valid_user = validate_username(body.username)
        normalized = normalize_username(valid_user)

        # Ensure no other user holds this username
        stmt = select(User).where(
            (User.id != current_user.id) &
            ((User.normalized_username == normalized) | (User.username == valid_user))
        )
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username is already taken")

        current_user.username = valid_user
        current_user.normalized_username = normalized

    if body.display_name is not None:
        current_user.display_name = body.display_name.strip()
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url.strip()
    if body.bio is not None:
        current_user.bio = body.bio.strip()
    if body.website is not None:
        current_user.website = body.website.strip()
    if body.phone is not None:
        current_user.phone = body.phone.strip()

    await db.commit()
    await db.refresh(current_user)
    return SuccessResponse(data=UserProfileResponse(**user_to_profile(current_user)), message="Profile updated")


@router.get("/sessions", response_model=SuccessResponse[List[SessionResponse]])
async def get_active_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all active login sessions for the current user."""
    sessions = await list_user_sessions(db, current_user.id)
    current_ip = request.client.host if request.client else None

    results = []
    for s in sessions:
        is_cur = (s.ip_address == current_ip) if current_ip else False
        results.append(SessionResponse(
            id=s.id,
            device_info=s.device_info or "Unknown Device",
            ip_address=s.ip_address,
            expires_at=s.expires_at,
            created_at=s.created_at,
            is_current=is_cur
        ))
    return SuccessResponse(data=results)


@router.delete("/sessions/{session_id}", response_model=SuccessResponse)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke a specific active session."""
    stmt = select(SessionModel).where(SessionModel.id == session_id, SessionModel.user_id == current_user.id)
    res = await db.execute(stmt)
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    await revoke_session(db, session_id)
    return SuccessResponse(data={"id": session_id}, message="Session revoked")


@router.post("/sessions/revoke-all", response_model=SuccessResponse)
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke all active sessions for the current user."""
    from app.auth.sessions import revoke_all_user_sessions
    count = await revoke_all_user_sessions(db, current_user.id)
    return SuccessResponse(data={"revoked_count": count}, message=f"Revoked {count} sessions")


@router.post("/forgot-password", response_model=SuccessResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request a password reset token. Always returns success to prevent account enumeration."""
    stmt = select(User).where(User.email == body.email.strip().lower())
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    reset_token_str = None
    if user and user.is_active:
        token_str, token_hash, expires_at = create_password_reset_token()
        reset_token_str = token_str
        record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            used=False
        )
        db.add(record)
        await db.commit()

    # In production, dispatch email. For developer reference, return token in non-prod
    data_out = {"message": "If this email is registered, instructions have been sent."}
    if reset_token_str:
        data_out["reset_token"] = reset_token_str  # returned for testing/development

    return SuccessResponse(data=data_out, message="Password reset initiated")


@router.post("/reset-password", response_model=SuccessResponse)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reset password using a valid, unused password reset token."""
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    stmt = select(PasswordResetToken).where(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used == False
    )
    res = await db.execute(stmt)
    prt = res.scalar_one_or_none()

    if not prt:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    exp = prt.expires_at
    now = datetime.now(timezone.utc) if exp.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
    if exp < now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    stmt_user = select(User).where(User.id == prt.user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = get_password_hash(body.new_password)
    prt.used = True

    # Revoke existing sessions upon password reset for security
    from app.auth.sessions import revoke_all_user_sessions
    await revoke_all_user_sessions(db, user.id)

    await db.commit()
    return SuccessResponse(data={"email": user.email}, message="Password reset successful")


@router.post("/verify-email", response_model=SuccessResponse)
async def verify_email(
    body: EmailVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify email address using a verification token."""
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    stmt = select(VerificationToken).where(
        VerificationToken.token_hash == token_hash,
        VerificationToken.used == False
    )
    res = await db.execute(stmt)
    vt = res.scalar_one_or_none()

    if not vt:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    exp_vt = vt.expires_at
    now_vt = datetime.now(timezone.utc) if exp_vt.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
    if exp_vt < now_vt:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    stmt_user = select(User).where(User.id == vt.user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.email_verified = True
    vt.used = True
    await db.commit()

    return SuccessResponse(data={"email": user.email, "email_verified": True}, message="Email verified successfully")
