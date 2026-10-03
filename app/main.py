import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError, ProviderError
from app.security.security import SecurityHeadersMiddleware, MaxBodySizeMiddleware
from app.security.rate_limit import default_rate_limiter

from app.api.routes import health, auth, records, projects, api_keys, audit, admin, storage, realtime

logger = logging.getLogger("shiv.main")

def create_app() -> FastAPI:
    app = FastAPI(
        title="SHIV Database & Auth V1",
        description="Centralized database and authentication infrastructure for the SHIV platform.",
        version="1.0.0",
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MaxBodySizeMiddleware, max_size=1024 * 1024 * 10) # 10MB limit

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        # We manually call rate limiter since middleware doesn't easily support FastAPI Depends
        # without complex workarounds, though using dependencies on routes is another option.
        try:
            await default_rate_limiter(request)
        except Exception as e:
            from fastapi import HTTPException
            if isinstance(e, HTTPException):
                return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        return await call_next(request)

    # Exception Handlers
    @app.exception_handler(AuthenticationError)
    async def auth_exception_handler(request: Request, exc: AuthenticationError):
        logger.warning(f"Authentication Error: {exc.message}")
        return JSONResponse(status_code=401, content={"detail": exc.message})

    @app.exception_handler(AuthorizationError)
    async def authz_exception_handler(request: Request, exc: AuthorizationError):
        logger.warning(f"Authorization Error: {exc.message}")
        return JSONResponse(status_code=403, content={"detail": exc.message})

    @app.exception_handler(ProviderError)
    async def provider_exception_handler(request: Request, exc: ProviderError):
        logger.error(f"Provider Error: {exc.message}")
        return JSONResponse(status_code=502, content={"detail": exc.message})

    @app.exception_handler(SQLAlchemyError)
    async def db_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"Database Error: {str(exc)}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # Routers
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(records.router)
    app.include_router(projects.router)
    app.include_router(api_keys.router)
    app.include_router(audit.router)
    app.include_router(admin.router)
    app.include_router(storage.router)
    app.include_router(realtime.router)

    return app

app = create_app()

@app.on_event("startup")
async def startup_event():
    logger.info("Starting SHIV DB & Auth service...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down SHIV DB & Auth service...")
