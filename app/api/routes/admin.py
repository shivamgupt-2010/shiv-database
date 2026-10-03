from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.database import get_db
from app.database.schemas.common import SuccessResponse
from app.database.models.auth import User
from app.api.dependencies import get_current_active_admin

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/users", response_model=SuccessResponse)
async def list_all_users(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """Admin-only endpoint to list all users in the system."""
    stmt = select(User)
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    data = [{
        "id": u.id,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active
    } for u in users]
    
    return SuccessResponse(data=data)
