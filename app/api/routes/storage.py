from fastapi import APIRouter, Depends, UploadFile, File
from app.database.schemas.common import SuccessResponse
from app.database.models.project import Project
from app.api.dependencies import get_project_by_api_key
from app.storage.service import StoragePoolService

router = APIRouter(prefix="/storage", tags=["Storage"])

# Define it as a dependency or instantiate it directly (since it just loads config)
storage_service = StoragePoolService()

@router.post("/upload", response_model=SuccessResponse)
async def upload_file(
    file: UploadFile = File(...),
    project: Project = Depends(get_project_by_api_key)
):
    file_bytes = await file.read()
    
    result = await storage_service.upload_file(
        project_id=project.id,
        file_name=file.filename,
        file_bytes=file_bytes,
        content_type=file.content_type
    )
    
    return SuccessResponse(data=result, message="File successfully uploaded to Storage Pool")
