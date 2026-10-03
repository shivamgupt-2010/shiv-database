from fastapi import APIRouter, Depends, Path
from typing import Any, Dict
from app.database.schemas.common import SuccessResponse
from app.database.schemas.records import QueryRequest
from app.database.models.project import Project
from app.database.models.auth import User
from app.database.service import DatabaseService
from app.audit.service import AuditService
from app.api.dependencies import get_database_service, get_project_by_api_key, get_current_user, get_audit_service

router = APIRouter(prefix="/data", tags=["Data/Records"])

@router.post("/{collection}", response_model=SuccessResponse)
async def create_record(
    collection: str,
    data: Dict[str, Any],
    project: Project = Depends(get_project_by_api_key),
    db_service: DatabaseService = Depends(get_database_service),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User = Depends(get_current_user)
):
    record = await db_service.create_record(project, collection, data)
    
    await audit_service.log_action(
        action="create_record",
        resource_type=f"collection:{collection}",
        resource_id=record["id"],
        project_id=project.id,
        actor_id=current_user.id
    )
    
    return SuccessResponse(data=record, message="Record created")


@router.get("/{collection}/{record_id}", response_model=SuccessResponse)
async def get_record(
    collection: str,
    record_id: str,
    project: Project = Depends(get_project_by_api_key),
    db_service: DatabaseService = Depends(get_database_service)
):
    record = await db_service.get_record(project, collection, record_id)
    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Record not found")
    return SuccessResponse(data=record)


@router.patch("/{collection}/{record_id}", response_model=SuccessResponse)
async def update_record(
    collection: str,
    record_id: str,
    data: Dict[str, Any],
    project: Project = Depends(get_project_by_api_key),
    db_service: DatabaseService = Depends(get_database_service),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User = Depends(get_current_user)
):
    record = await db_service.update_record(project, collection, record_id, data)
    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Record not found")
        
    await audit_service.log_action(
        action="update_record",
        resource_type=f"collection:{collection}",
        resource_id=record["id"],
        project_id=project.id,
        actor_id=current_user.id
    )
        
    return SuccessResponse(data=record)


@router.delete("/{collection}/{record_id}", response_model=SuccessResponse)
async def delete_record(
    collection: str,
    record_id: str,
    project: Project = Depends(get_project_by_api_key),
    db_service: DatabaseService = Depends(get_database_service),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User = Depends(get_current_user)
):
    success = await db_service.delete_record(project, collection, record_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Record not found")
        
    await audit_service.log_action(
        action="delete_record",
        resource_type=f"collection:{collection}",
        resource_id=record_id,
        project_id=project.id,
        actor_id=current_user.id
    )
        
    return SuccessResponse(data={"deleted": True}, message="Record deleted")


@router.post("/{collection}/query", response_model=SuccessResponse)
async def query_records(
    collection: str,
    query: QueryRequest,
    project: Project = Depends(get_project_by_api_key),
    db_service: DatabaseService = Depends(get_database_service)
):
    records = await db_service.query_records(project, collection, query)
    return SuccessResponse(data={"items": records, "count": len(records)})
