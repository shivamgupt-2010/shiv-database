from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None
    primary_provider: str = Field(default="shiv_native")
    fallback_provider: Optional[str] = None
    enabled_providers: List[str] = Field(default_factory=lambda: ["shiv_native"])


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    primary_provider: Optional[str] = None
    fallback_provider: Optional[str] = None
    enabled_providers: Optional[List[str]] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    primary_provider: str
    fallback_provider: Optional[str] = None
    enabled_providers: List[str]
    status: str
    created_at: datetime
    updated_at: datetime


class APIKeyCreateRequest(BaseModel):
    key_name: str = Field(min_length=2, max_length=100)
    scopes: List[str] = Field(default_factory=lambda: ["database:read", "database:write"])
    expires_in_days: Optional[int] = Field(default=None, ge=1)


class APIKeyResponse(BaseModel):
    id: str
    project_id: str
    key_name: str
    key_prefix: str
    scopes: List[str]
    expires_at: Optional[datetime] = None
    revoked: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime


class APIKeyCreatedSecretResponse(APIKeyResponse):
    secret_key: str  # Displayed ONLY ONCE upon creation!
