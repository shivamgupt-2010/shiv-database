from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.session import get_db_session as get_db
from app.database.schemas.common import SuccessResponse
from app.database.schemas.projects import ProjectCreateRequest
from app.database.models.project import Project
from app.database.models.auth import User
from app.api.dependencies import get_current_user
import uuid

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("/", response_model=SuccessResponse)
async def create_project(
    body: ProjectCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if project with same name already exists for this user
    stmt = select(Project).where(Project.name == body.name, Project.owner_id == current_user.id)
    result = await db.execute(stmt)
    existing_project = result.scalar_one_or_none()
    if existing_project:
        return SuccessResponse(data={"id": existing_project.id, "name": existing_project.name}, message="Project already exists")

    enabled_prov = body.enabled_providers
    if isinstance(enabled_prov, list):
        enabled_prov_str = ",".join(enabled_prov)
    else:
        enabled_prov_str = str(enabled_prov or "shiv_native")

    project = Project(
        name=body.name,
        description=body.description,
        primary_provider=body.primary_provider or "shiv_native",
        fallback_provider=body.fallback_provider,
        enabled_providers=enabled_prov_str,
        owner_id=current_user.id
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    return SuccessResponse(data={"id": project.id, "name": project.name}, message="Project created")


@router.get("/", response_model=SuccessResponse)
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Project).where(
        Project.status == "active",
        Project.owner_id == current_user.id
    ).order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    projects = result.scalars().all()
    
    data = [{"id": p.id, "name": p.name, "primary_provider": p.primary_provider, "description": p.description or ""} for p in projects]
    return SuccessResponse(data=data)


@router.delete("/{project_id}", response_model=SuccessResponse)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Project).where(Project.id == project_id, Project.owner_id == current_user.id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.status = "deleted"
    await db.commit()
    return SuccessResponse(message="Project deleted")
