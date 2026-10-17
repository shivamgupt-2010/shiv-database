from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database.models.audit import AuditLog
import json

class AuditService:
    """Service to record and query audit logs for compliance and debugging."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        project_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "success"
    ) -> AuditLog:
        """Record an action in the audit log."""
        import uuid
        req_id = str(uuid.uuid4())
        details = metadata or {}
        if resource_id:
            details["resource_id"] = resource_id
        if actor_id:
            details["actor_id"] = actor_id

        log_entry = AuditLog(
            request_id=req_id,
            project_id=project_id,
            user_id=actor_id if (actor_id and not str(actor_id).startswith("api_key:")) else None,
            event_type=resource_type,
            operation=action,
            resource=f"{resource_type}:{resource_id}" if resource_id else resource_type,
            provider="shiv_native",
            status=status,
            details_json=json.dumps(details),
            ip_address=ip_address
        )
        self.db.add(log_entry)
        await self.db.commit()
        await self.db.refresh(log_entry)
        return log_entry

    async def query_logs(
        self,
        project_id: str,
        action: Optional[str] = None,
        actor_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AuditLog]:
        """Query audit logs for a project."""
        stmt = select(AuditLog).where(AuditLog.project_id == project_id)
        
        if action:
            stmt = stmt.where(AuditLog.operation == action)
        if actor_id:
            stmt = stmt.where(AuditLog.user_id == actor_id)
            
        stmt = stmt.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
