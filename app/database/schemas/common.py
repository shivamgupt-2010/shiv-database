from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field
from app.core.constants import ErrorCode

T = TypeVar("T")


class MetaResponse(BaseModel):
    request_id: str
    count: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    provider: Optional[str] = None


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    meta: MetaResponse


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    request_id: str
    details: Optional[Any] = None


class ApiErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
