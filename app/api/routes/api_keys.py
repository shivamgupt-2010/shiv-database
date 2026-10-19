from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database.session import get_db_session as get_db
from app.database.schemas.common import SuccessResponse
from app.database.models.auth import User
from app.database.models.project import APIKey, Project
from app.api.dependencies import get_current_user
from app.security.api_keys import generate_api_key

router = APIRouter(prefix="/api-keys", tags=["API Keys"])

from fastapi import Request
from typing import Optional

@router.get("/{project_id}", response_model=SuccessResponse)
async def list_api_keys(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify project exists by id or by name AND belongs to current_user
    stmt = select(Project).where(
        ((Project.id == project_id) | (Project.name == project_id)) & (Project.owner_id == current_user.id)
    )
    result = await db.execute(stmt)
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    stmt_keys = select(APIKey).where(APIKey.project_id == proj.id).order_by(APIKey.created_at.desc())
    result_keys = await db.execute(stmt_keys)
    keys = result_keys.scalars().all()

    data = [
        {
            "id": k.id,
            "name": k.key_name,
            "key_prefix": k.key_prefix,
            "revoked": k.revoked,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None
        }
        for k in keys
    ]
    return SuccessResponse(data=data)


@router.post("/{project_id}", response_model=SuccessResponse)
async def create_api_key(
    project_id: str,
    request: Request,
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # If name was not provided as query param, check JSON body
    if not name:
        try:
            body_json = await request.json()
            name = body_json.get("name") or body_json.get("key_name")
        except Exception:
            pass
    if not name:
        name = "Production Key"

    # Verify project exists by id or by name AND belongs to current_user
    stmt = select(Project).where(
        ((Project.id == project_id) | (Project.name == project_id)) & (Project.owner_id == current_user.id)
    )
    result = await db.execute(stmt)
    proj = result.scalar_one_or_none()
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
        data={"id": api_key.id, "name": api_key.name, "raw_key": raw_key, "key_prefix": prefix},
        message="API Key created. Save this raw_key now; it won't be shown again."
    )


@router.delete("/{key_id}", response_model=SuccessResponse)
async def revoke_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = (
        select(APIKey)
        .join(Project, APIKey.project_id == Project.id)
        .where(APIKey.id == key_id, Project.owner_id == current_user.id)
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    api_key.revoked = True
    await db.commit()
    return SuccessResponse(message="API Key revoked")
