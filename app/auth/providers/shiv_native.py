from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.auth.providers.base import AuthProvider
from app.database.models.auth import User
from app.auth.password import get_password_hash, verify_password
from app.core.exceptions import AuthenticationError
from app.auth.username import validate_username, normalize_username
from app.auth.identity import generate_unique_shiv_id

class ShivNativeAuthProvider(AuthProvider):
    """Native authentication provider using PostgreSQL/SQLite and Argon2id."""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, user_data: Dict[str, Any]) -> User:
        email = user_data.get("email", "").strip().lower()
        raw_username = user_data.get("username", "").strip()
        password = user_data.get("password")
        meta = user_data.get("metadata") or {}
        display_name = user_data.get("display_name") or meta.get("display_name") or raw_username
        phone = user_data.get("phone") or meta.get("phone")

        # Validate username syntax and reserved list
        valid_username = validate_username(raw_username)
        normalized_user = normalize_username(valid_username)

        # Check if email already registered
        existing_email = await self.get_user_by_email(email)
        if existing_email:
            raise AuthenticationError("User with this email already exists")

        # Check if normalized username already taken
        stmt_user = select(User).where((User.normalized_username == normalized_user) | (User.username == valid_username))
        res_user = await self.db.execute(stmt_user)
        if res_user.scalar_one_or_none():
            raise AuthenticationError("Username is already taken")

        # If this is the very first user in the database, make them a super_admin
        count_stmt = select(User).limit(1)
        first_user_check = await self.db.execute(count_stmt)
        is_first_user = first_user_check.scalar_one_or_none() is None

        shiv_id = await generate_unique_shiv_id(self.db)
        hashed_password = get_password_hash(password)

        new_user = User(
            shiv_id=shiv_id,
            email=email,
            username=valid_username,
            normalized_username=normalized_user,
            display_name=display_name,
            phone=phone,
            hashed_password=hashed_password,
            role="super_admin" if is_first_user else "user",
            status="active",
        )
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user

    async def authenticate_user(self, credentials: Dict[str, Any]) -> User:
        identifier = credentials.get("email_or_username", "").strip()
        password = credentials.get("password")

        if not identifier or not password:
            raise AuthenticationError("Invalid identifier or password")

        clean_id = identifier.lower()

        # Query by normalized email or normalized username or shiv_id
        stmt = select(User).where(
            (User.email == clean_id)
            | (User.normalized_username == clean_id)
            | (User.username == identifier)
            | (User.shiv_id == identifier.upper())
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.hashed_password:
            raise AuthenticationError("Invalid email, username, or password")

        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email, username, or password")

        if user.status != "active":
            raise AuthenticationError(f"User account is {user.status}")

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
            user.hashed_password = get_password_hash(data["password"])
        if "email" in data:
            user.email = data["email"]
        if "status" in data:
            user.status = data["status"]
        if "email_verified" in data:
            user.email_verified = data["email_verified"]
            
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
