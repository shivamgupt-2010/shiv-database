from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database.database import get_db
from app.database.schemas.common import SuccessResponse
from app.database.models.auth import APIKey, User
from app.api.dependencies import get_current_active_admin
from app.security.api_keys import generate_api_key

router = APIRouter(prefix="/api-keys", tags=["API Keys"])

@router.post("/{project_id}", response_model=SuccessResponse)
async def create_api_key(
    project_id: str,
    name: str,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    raw_key, key_hash = generate_api_key()
    
    api_key = APIKey(
        project_id=project_id,
        key_hash=key_hash,
        name=name
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    
    return SuccessResponse(
        data={"id": api_key.id, "name": api_key.name, "raw_key": raw_key},
        message="API Key created. Save this raw_key now; it won't be shown again."
    )


@router.delete("/{key_id}", response_model=SuccessResponse)
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    stmt = update(APIKey).where(APIKey.id == key_id).values(is_revoked=True)
    result = await db.execute(stmt)
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    return SuccessResponse(message="API Key revoked")
