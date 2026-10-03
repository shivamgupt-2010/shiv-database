from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.auth.providers.base import AuthProvider
from app.database.models.auth import User
from app.auth.password import get_password_hash, verify_password
from app.core.exceptions import AuthenticationError

class ShivNativeAuthProvider(AuthProvider):
    """Native authentication provider using PostgreSQL/SQLite and Argon2id."""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, user_data: Dict[str, Any]) -> User:
        email = user_data.get("email")
        password = user_data.get("password")
        metadata = user_data.get("metadata", {})
        
        # Check if user exists
        existing = await self.get_user_by_email(email)
        if existing:
            raise AuthenticationError("User with this email already exists")
            
        hashed_password = get_password_hash(password)
        new_user = User(
            email=email,
            password_hash=hashed_password,
            metadata_=metadata
        )
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user

    async def authenticate_user(self, credentials: Dict[str, Any]) -> User:
        email = credentials.get("email")
        password = credentials.get("password")
        
        user = await self.get_user_by_email(email)
        if not user or not user.password_hash:
            raise AuthenticationError("Invalid email or password")
            
        if not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
            
        if not user.is_active:
            raise AuthenticationError("User account is inactive")
            
        return user

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_user(self, user_id: str, data: Dict[str, Any]) -> User:
        user = await self.get_user_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found")
            
        if "password" in data:
            user.password_hash = get_password_hash(data["password"])
        if "email" in data:
            user.email = data["email"]
        if "metadata_" in data:
            user.metadata_ = data["metadata_"]
        if "is_active" in data:
            user.is_active = data["is_active"]
        if "is_verified" in data:
            user.is_verified = data["is_verified"]
            
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete_user(self, user_id: str) -> bool:
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        await self.db.delete(user)
        await self.db.commit()
        return True
