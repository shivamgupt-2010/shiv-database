from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.providers.shiv_native import ShivNativeAuthProvider
from app.auth.tokens import create_access_token, create_refresh_token
from app.auth.sessions import create_session, revoke_session, get_valid_session_by_token_hash
from app.database.models.auth import User
from app.database.models.project import Project
from app.core.exceptions import AuthenticationError

class AuthService:
    """Service to coordinate Unified Authentication across the Data Fabric."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        # Unified Data Fabric uses a single global identity pool 
        # so users can traverse apps seamlessly. We use Native provider to keep it free and unlimited.
        self.provider = ShivNativeAuthProvider(db)

    async def register(self, email: str, password: str, metadata: Optional[Dict[str, Any]] = None, project: Optional[Project] = None) -> User:
        # Project parameter is ignored because auth is global across all projects
        return await self.provider.register_user({
            "email": email, 
            "password": password, 
            "metadata": metadata or {}
        })

    async def login(
        self, 
        email: str, 
        password: str, 
        project: Optional[Project] = None,
        ip_address: str = None,
        user_agent: str = None
    ) -> Tuple[str, str, User]:
        user = await self.provider.authenticate_user({"email": email, "password": password})
        
        access_token, _ = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
        refresh_token, refresh_token_hash, expire = create_refresh_token()
        
        await create_session(self.db, user.id, refresh_token_hash, expire, ip_address, user_agent)
        
        return access_token, refresh_token, user

    async def refresh_tokens(self, refresh_token: str, ip_address: str = None, user_agent: str = None) -> Tuple[str, str]:
        import hashlib
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        session = await get_valid_session_by_token_hash(self.db, token_hash)
        await revoke_session(self.db, session.id)
        
        user = await self.provider.get_user_by_id(session.user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User is no longer active")
            
        access_token, _ = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
        new_refresh_token, new_refresh_token_hash, expire = create_refresh_token()
        
        await create_session(self.db, user.id, new_refresh_token_hash, expire, ip_address, user_agent)
        
        return access_token, new_refresh_token

    async def logout(self, refresh_token: str) -> bool:
        import hashlib
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        try:
            session = await get_valid_session_by_token_hash(self.db, token_hash)
            return await revoke_session(self.db, session.id)
        except AuthenticationError:
            return False

    async def verify_user_token(self, token: str) -> Dict[str, Any]:
        from app.auth.tokens import verify_access_token
        return verify_access_token(token)
