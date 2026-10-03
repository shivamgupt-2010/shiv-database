from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import datetime, timezone
from app.database.models.auth import Session as SessionModel
from app.core.exceptions import AuthenticationError

async def create_session(
    db: AsyncSession, 
    user_id: str, 
    refresh_token_hash: str, 
    expires_at: datetime, 
    ip_address: str = None, 
    user_agent: str = None
) -> SessionModel:
    """Create a new user session."""
    session_record = SessionModel(
        user_id=user_id,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.add(session_record)
    await db.commit()
    await db.refresh(session_record)
    return session_record

async def revoke_session(db: AsyncSession, session_id: str) -> bool:
    """Revoke a specific session."""
    stmt = update(SessionModel).where(SessionModel.id == session_id).values(is_revoked=True)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0

async def revoke_all_user_sessions(db: AsyncSession, user_id: str) -> int:
    """Revoke all sessions for a user (e.g., on password reset or account compromise)."""
    stmt = update(SessionModel).where(SessionModel.user_id == user_id).values(is_revoked=True)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount

async def get_valid_session_by_token_hash(db: AsyncSession, token_hash: str) -> SessionModel:
    """Retrieve a session by token hash, ensuring it is valid and not expired/revoked."""
    stmt = select(SessionModel).where(SessionModel.refresh_token_hash == token_hash)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    
    if not session:
        raise AuthenticationError("Session not found")
        
    if session.is_revoked:
        raise AuthenticationError("Session has been revoked")
        
    if session.expires_at < datetime.now(timezone.utc):
        raise AuthenticationError("Session has expired")
        
    return session
