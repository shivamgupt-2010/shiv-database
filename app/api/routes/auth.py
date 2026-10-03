from fastapi import APIRouter, Depends, Request
from app.database.schemas.auth import UserRegisterRequest, UserLoginRequest, TokenResponse
from app.database.schemas.common import SuccessResponse
from app.database.models.project import Project
from app.database.models.auth import User
from app.auth.service import AuthService
from app.api.dependencies import get_auth_service, get_optional_project_by_api_key, get_current_user
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=SuccessResponse)
async def register(
    body: UserRegisterRequest,
    project: Optional[Project] = Depends(get_optional_project_by_api_key),
    auth_service: AuthService = Depends(get_auth_service)
):
    user = await auth_service.register(body.email, body.password, body.metadata, project)
    return SuccessResponse(data={"id": user.id, "email": user.email}, message="User registered successfully")


@router.post("/login", response_model=SuccessResponse[TokenResponse])
async def login(
    request: Request,
    body: UserLoginRequest,
    project: Optional[Project] = Depends(get_optional_project_by_api_key),
    auth_service: AuthService = Depends(get_auth_service)
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    
    access_token, refresh_token, user = await auth_service.login(
        body.email, body.password, project, ip, ua
    )
    
    return SuccessResponse(
        data=TokenResponse(access_token=access_token, refresh_token=refresh_token, token_type="bearer")
    )


@router.post("/refresh", response_model=SuccessResponse[TokenResponse])
async def refresh(
    request: Request,
    refresh_token: str,
    auth_service: AuthService = Depends(get_auth_service)
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    
    access_token, new_refresh_token = await auth_service.refresh_tokens(refresh_token, ip, ua)
    
    return SuccessResponse(
        data=TokenResponse(access_token=access_token, refresh_token=new_refresh_token, token_type="bearer")
    )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    refresh_token: str,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user)
):
    success = await auth_service.logout(refresh_token)
    return SuccessResponse(data={"success": success}, message="Logged out successfully")


@router.get("/me", response_model=SuccessResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return SuccessResponse(data={
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "metadata": current_user.metadata_
    })
