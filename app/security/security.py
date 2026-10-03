from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add standard security headers to every response.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Standard security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # CSP can be configured in settings if needed
        # response.headers["Content-Security-Policy"] = settings.CSP_HEADER
        
        return response

class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to prevent excessively large payload sizes (DDoS protection).
    """
    def __init__(self, app, max_size: int = 1024 * 1024 * 10): # Default 10MB
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        if "content-length" in request.headers:
            content_length = int(request.headers.get("content-length", 0))
            if content_length > self.max_size:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Payload too large"}
                )
        return await call_next(request)
