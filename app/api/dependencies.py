from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database.session import get_db_session as get_db
from app.auth.service import AuthService
from app.database.service import DatabaseService
from app.audit.service import AuditService
from app.database.models.auth import User
from app.database.models.project import Project
from app.security.api_keys import verify_api_key

# Dependency to get AuthService
def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)

# Dependency to get DatabaseService
def get_database_service(db: AsyncSession = Depends(get_db)) -> DatabaseService:
    return DatabaseService(db)

# Dependency to get AuditService
def get_audit_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    return AuditService(db)

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to get the current authenticated user via JWT."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    try:
        payload = await auth_service.verify_user_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
            
        # Get native provider to fetch user record (since JWT maps to our local DB User record)
        # Even if Firebase authenticated originally, SHIV Auth synchronizes users.
        native_provider = auth_service._get_provider()
        user = await native_provider.get_user_by_id(user_id)
        
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
            
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency ensuring user is an admin."""
    from app.core.constants import RoleEnum
    if current_user.role not in [RoleEnum.ADMIN.value, RoleEnum.SUPER_ADMIN.value]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return current_user

async def get_project_by_api_key(
    x_api_key: Optional[str] = Header(None, description="Project API Key"),
    db: AsyncSession = Depends(get_db)
) -> Project:
    """Dependency to validate x-api-key and retrieve the corresponding Project."""
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="x-api-key header missing")
        
    try:
        api_key_record = await verify_api_key(db, x_api_key)
        
        stmt = select(Project).where(Project.id == api_key_record.project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if not project.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project is disabled")
            
        return project
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

async def get_optional_project_by_api_key(
    x_api_key: Optional[str] = Header(None, description="Project API Key"),
    db: AsyncSession = Depends(get_db)
) -> Optional[Project]:
    """Dependency for optional API key (e.g. for global Admin login)"""
    if not x_api_key:
        return None
    try:
        return await get_project_by_api_key(x_api_key, db)
    except HTTPException:
        return None
