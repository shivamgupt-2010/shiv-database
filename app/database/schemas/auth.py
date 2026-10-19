from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    display_name: Optional[str] = None
    phone: Optional[str] = None
    metadata: Optional[dict] = None


class UserLoginRequest(BaseModel):
    email_or_username: str
    password: str


class UserProfileResponse(BaseModel):
    id: str
    shiv_id: Optional[str] = None
    email: str
    username: str
    normalized_username: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    phone_verified: Optional[bool] = False
    avatar_url: Optional[str] = None
    email_verified: bool = False
    role: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    username: Optional[str] = Field(default=None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    expires_at: datetime
    created_at: datetime
    is_current: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = 3600
    user: Optional[UserProfileResponse] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class EmailVerifyRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)
