from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.database import get_db
from app.database.schemas.common import SuccessResponse
from app.database.schemas.project import ProjectCreateRequest
from app.database.models.project import Project
from app.database.models.auth import User
from app.api.dependencies import get_current_active_admin
import uuid

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("/", response_model=SuccessResponse)
async def create_project(
    body: ProjectCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    project = Project(
        name=body.name,
        description=body.description,
        primary_provider=body.primary_provider,
        fallback_provider=body.fallback_provider,
        auth_provider=body.auth_provider,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    return SuccessResponse(data={"id": project.id, "name": project.name}, message="Project created")


@router.get("/", response_model=SuccessResponse)
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    stmt = select(Project).where(Project.is_active == True)
    result = await db.execute(stmt)
    projects = result.scalars().all()
    
    data = [{"id": p.id, "name": p.name, "primary_provider": p.primary_provider} for p in projects]
    return SuccessResponse(data=data)
