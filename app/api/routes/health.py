from fastapi import APIRouter, Depends
from typing import Dict, Any
from app.database.service import DatabaseService
from app.api.dependencies import get_database_service

router = APIRouter(prefix="/health", tags=["System"])

@router.get("/")
async def health_check() -> Dict[str, str]:
    """Basic service health check."""
    return {"status": "ok", "service": "SHIV Database & Auth V1"}

@router.get("/db")
async def db_health_check(db_service: DatabaseService = Depends(get_database_service)) -> Dict[str, Any]:
    """Check health of all registered database providers."""
    statuses = await db_service.health_check_providers()
    return {
        "status": "ok" if all(s == "healthy" for s in statuses.values()) else "degraded",
        "providers": statuses
    }
