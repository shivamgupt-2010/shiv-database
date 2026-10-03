from fastapi import APIRouter, Depends
from typing import List, Optional
from app.database.schemas.common import SuccessResponse
from app.database.models.project import Project
from app.api.dependencies import get_project_by_api_key, get_audit_service
from app.audit.service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit Logs"])

@router.get("/", response_model=SuccessResponse)
async def get_project_audit_logs(
    action: Optional[str] = None,
    actor_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    project: Project = Depends(get_project_by_api_key),
    audit_service: AuditService = Depends(get_audit_service)
):
    logs = await audit_service.query_logs(
        project_id=project.id,
        action=action,
        actor_id=actor_id,
        limit=limit,
        offset=offset
    )
    
    data = [{
        "id": log.id,
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "actor_id": log.actor_id,
        "metadata": log.metadata_,
        "created_at": log.created_at
    } for log in logs]
    
    return SuccessResponse(data=data)
