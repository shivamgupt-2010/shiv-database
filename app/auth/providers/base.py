from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.database.models.auth import User

class AuthProvider(ABC):
    """Abstract base class for Authentication providers."""
    
    @abstractmethod
    async def register_user(self, user_data: Dict[str, Any]) -> Any:
        """Register a new user."""
        pass
        
    @abstractmethod
    async def authenticate_user(self, credentials: Dict[str, Any]) -> Any:
        """Authenticate a user and return the user record."""
        pass
        
    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Retrieve a user by their ID."""
        pass
        
    @abstractmethod
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieve a user by their email address."""
        pass

    @abstractmethod
    async def update_user(self, user_id: str, data: Dict[str, Any]) -> User:
        """Update user metadata, password, or status."""
        pass
        
    @abstractmethod
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user account."""
        pass
