import logging
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Header, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.session import get_db_session as get_db
from app.database.schemas.common import SuccessResponse
from app.database.models.project import Project
from app.storage.service import StoragePoolService
from app.security.api_keys import verify_api_key
from app.auth.service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/storage", tags=["Storage"])
storage_service = StoragePoolService()


async def resolve_project_context(
    request: Request,
    project_id: Optional[str] = Query(None, description="Project ID (required if using Bearer token)"),
    x_api_key: Optional[str] = Header(None, description="Project API Key"),
    db: AsyncSession = Depends(get_db)
) -> Project:
    """
    Resolves project context via either x-api-key header or Authorization: Bearer <jwt> token.
    Allows both external apps (API key) and dashboard UI (JWT session) to manage files.
    """
    # 1. Check API Key
    if x_api_key:
        try:
            api_key_record = await verify_api_key(db, x_api_key)
            stmt = select(Project).where(Project.id == api_key_record.project_id)
            res = await db.execute(stmt)
            project = res.scalar_one_or_none()
            if not project or not project.is_active:
                raise HTTPException(status_code=403, detail="Invalid or disabled project for this API key")
            return project
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid API Key: {str(e)}")

    # 2. Check JWT Bearer token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        auth_service = AuthService(db)
        try:
            payload = await auth_service.verify_user_token(token)
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token payload")

            if project_id:
                stmt = select(Project).where((Project.id == project_id) | (Project.name == project_id))
            else:
                stmt = select(Project).where(Project.status == "active").order_by(Project.created_at.desc())

            res = await db.execute(stmt)
            project = res.scalar_one_or_none()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            return project
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide 'x-api-key' header or 'Authorization: Bearer <token>'."
    )


@router.post("/upload", response_model=SuccessResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    project: Project = Depends(resolve_project_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a file or image to SHIV Native Persistent Storage.
    Zero external dependencies, 100% free, no credit card or Firebase storage bucket needed.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file cannot be empty")

    # Determine base URL dynamically (e.g. https://shiv-database.onrender.com)
    base_url = str(request.base_url).rstrip("/")

    result = await storage_service.upload_file(
        db=db,
        project_id=project.id,
        file_name=file.filename or "unnamed_file",
        file_bytes=file_bytes,
        content_type=file.content_type or "application/octet-stream",
        base_url=base_url
    )

    return SuccessResponse(
        data=result,
        message="File successfully uploaded to SHIV Native Storage"
    )


@router.get("/file/{file_id}")
async def get_file_content(
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Public raw media endpoint. Serves image or file bytes directly with caching headers.
    No authentication required - ideal for <img> tags and public asset links.
    """
    file_data = await storage_service.get_file(db, file_id)
    if not file_data:
        raise HTTPException(status_code=404, detail="File not found")

    file_bytes, content_type, file_name = file_data

    headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": f'inline; filename="{file_name}"',
    }

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers=headers
    )


@router.get("/list", response_model=SuccessResponse)
async def list_files(
    request: Request,
    project: Project = Depends(resolve_project_context),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    List files stored for the authenticated project.
    """
    base_url = str(request.base_url).rstrip("/")
    files = await storage_service.list_files(
        db=db,
        project_id=project.id,
        base_url=base_url,
        limit=limit,
        offset=offset
    )
    return SuccessResponse(data=files)


@router.delete("/file/{file_id}", response_model=SuccessResponse)
async def delete_file(
    file_id: str,
    project: Project = Depends(resolve_project_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a stored file by ID.
    """
    success = await storage_service.delete_file(db, file_id, project_id=project.id)
    if not success:
        raise HTTPException(status_code=404, detail="File not found or already deleted")

    return SuccessResponse(data={"id": file_id}, message="File deleted successfully")
