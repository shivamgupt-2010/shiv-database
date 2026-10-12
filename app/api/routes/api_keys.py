from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database.session import get_db_session as get_db
from app.database.schemas.common import SuccessResponse
from app.database.models.auth import User
from app.database.models.project import APIKey, Project
from app.api.dependencies import get_current_active_admin
from app.security.api_keys import generate_api_key

router = APIRouter(prefix="/api-keys", tags=["API Keys"])

@router.post("/{project_id}", response_model=SuccessResponse)
async def create_api_key(
    project_id: str,
    name: str = "Production Key",
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    # Verify project exists by id or by name
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    proj = result.scalar_one_or_none()
    if not proj:
        stmt2 = select(Project).where(Project.name == project_id)
        result2 = await db.execute(stmt2)
        proj = result2.scalar_one_or_none()
        
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        
    target_project_id = proj.id

    raw_key, key_hash = generate_api_key()
    
    prefix = raw_key[:10]
    api_key = APIKey(
        project_id=target_project_id,
        key_hash=key_hash,
        key_name=name,
        key_prefix=prefix
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
    stmt = update(APIKey).where(APIKey.id == key_id).values(revoked=True)
    result = await db.execute(stmt)
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    return SuccessResponse(message="API Key revoked")
