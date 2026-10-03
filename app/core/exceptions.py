from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from app.core.constants import ErrorCode


class ShivException(HTTPException):
    """Base exception for SHIV Database & Auth Platform."""

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or {}


class AuthenticationError(ShivException):
    def __init__(self, message: str = "Authentication required", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.UNAUTHORIZED,
            message=message,
            details=details,
        )


class PermissionDeniedError(ShivException):
    def __init__(self, message: str = "Insufficient permissions", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=ErrorCode.FORBIDDEN,
            message=message,
            details=details,
        )


class NotFoundError(ShivException):
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.NOT_FOUND,
            message=message,
            details=details,
        )


class BadRequestError(ShivException):
    def __init__(self, message: str = "Invalid request", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.BAD_REQUEST,
            message=message,
            details=details,
        )


class ConflictError(ShivException):
    def __init__(self, message: str = "Resource conflict", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code=ErrorCode.CONFLICT,
            message=message,
            details=details,
        )


class RateLimitExceededError(ShivException):
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            details=details,
        )


class ProviderError(ShivException):
    def __init__(self, message: str = "Database provider failure", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code=ErrorCode.PROVIDER_ERROR,
            message=message,
            details=details,
        )
