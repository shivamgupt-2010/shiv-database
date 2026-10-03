import secrets
import hashlib
from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models.auth import APIKey
from app.core.exceptions import AuthorizationError

def generate_api_key(prefix: str = "shiv_sk_") -> Tuple[str, str]:
    """
    Generate a new API key and its hash.
    Returns: (raw_key, hashed_key)
    """
    raw_key = prefix + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash

async def verify_api_key(db: AsyncSession, raw_key: str) -> APIKey:
    """
    Verify an API key against the database and return the APIKey record.
    """
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    
    stmt = select(APIKey).where(APIKey.key_hash == key_hash)
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise AuthorizationError("Invalid API key")
        
    if api_key.is_revoked:
        raise AuthorizationError("API key has been revoked")
        
    if api_key.expires_at and api_key.expires_at.timestamp() < __import__("time").time():
         raise AuthorizationError("API key has expired")
         
    return api_key
