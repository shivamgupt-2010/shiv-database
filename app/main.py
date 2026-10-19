import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError, ProviderError
from app.security.security import SecurityHeadersMiddleware, MaxBodySizeMiddleware
from app.security.rate_limit import default_rate_limiter

from app.api.routes import (
    health,
    auth,
    records,
    projects,
    api_keys,
    audit,
    admin,
    storage,
    realtime,
    dashboard,
    oidc,
    oauth,
    oauth_clients,
)
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("shiv.main")

def create_app() -> FastAPI:
    app = FastAPI(
        title="SHIV Identity & Unified Auth Platform",
        description="Centralized OpenID Connect and OAuth 2.0 Identity Platform for SHIV products and external websites.",
        version="2.0.0",
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
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

    @app.exception_handler(PermissionDeniedError)
    async def authz_exception_handler(request: Request, exc: PermissionDeniedError):
        logger.warning(f"Authorization Error: {exc.message}")
        return JSONResponse(status_code=403, content={"detail": exc.message})

    @app.exception_handler(ProviderError)
    async def provider_exception_handler(request: Request, exc: ProviderError):
        logger.error(f"Provider Error: {exc.message}")
        return JSONResponse(status_code=502, content={"detail": exc.message})

    @app.exception_handler(SQLAlchemyError)
    async def db_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"Database Error: {str(exc)}")
        detail = str(exc) if settings.DEBUG else "Internal server error"
        return JSONResponse(status_code=500, content={"detail": detail})

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled Exception: {str(exc)}")
        detail = str(exc) if settings.DEBUG else "Internal server error"
        return JSONResponse(status_code=500, content={"detail": detail})

    # Routers
    app.include_router(health.router)
    app.include_router(oidc.router)
    app.include_router(oauth.router)
    app.include_router(oauth_clients.router)
    app.include_router(auth.router)
    app.include_router(records.router)
    app.include_router(projects.router)
    app.include_router(api_keys.router)
    app.include_router(audit.router)
    app.include_router(admin.router)
    app.include_router(storage.router)
    app.include_router(realtime.router)
    app.include_router(dashboard.router)

    # Static files for dashboard
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    return app

app = create_app()

@app.on_event("startup")
async def startup_event():
    logger.info("Starting SHIV Identity & Auth service...")
    try:
        from app.database.session import engine
        from app.database.models.base import Base
        from sqlalchemy import text
        import app.database.models.auth
        import app.database.models.project
        import app.database.models.record
        import app.database.models.audit
        import app.database.models.fabric
        import app.database.models.media
        import app.database.models.oauth
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Safe schema migrations for new SHIV Identity columns (isolated transactions)
        is_postgres = "postgresql" in str(engine.url)
        ddl_statements = [
            ("users", "shiv_id", "VARCHAR(20)"),
            ("users", "normalized_username", "VARCHAR(100)"),
            ("users", "display_name", "VARCHAR(255)"),
            ("users", "bio", "TEXT"),
            ("users", "website", "VARCHAR(255)"),
            ("users", "phone", "VARCHAR(50)"),
            ("users", "phone_verified", "BOOLEAN DEFAULT FALSE"),
            ("users", "mfa_enabled", "BOOLEAN DEFAULT FALSE"),
            ("users", "mfa_secret", "VARCHAR(128)"),
            ("sessions", "refresh_token_hash", "VARCHAR(255)"),
            ("projects", "owner_id", "VARCHAR(36)"),
        ]

        for table, col_name, col_type in ddl_statements:
            try:
                async with engine.begin() as ddl_conn:
                    if is_postgres:
                        await ddl_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    else:
                        await ddl_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
            except Exception:
                pass

        # Seed or promote admin@shiv.com to super_admin with SHIV ID
        from app.database.session import AsyncSessionLocal
        from app.database.models.auth import User
        from app.auth.password import get_password_hash
        from sqlalchemy import select, update

        async with AsyncSessionLocal() as session:
            stmt = select(User).where((User.email == "admin@shiv.com") | (User.username == "admin"))
            res = await session.execute(stmt)
            admin_user = res.scalar_one_or_none()
            if admin_user:
                admin_user.email = "admin@shiv.com"
                admin_user.username = "admin"
                admin_user.normalized_username = "admin"
                if not admin_user.shiv_id:
                    admin_user.shiv_id = "SHV-10001"
                if not admin_user.display_name:
                    admin_user.display_name = "SHIV Administrator"
                admin_user.role = "super_admin"
                admin_user.status = "active"
                admin_user.hashed_password = get_password_hash("shivadmin")
                await session.commit()
                admin_id = admin_user.id
            else:
                new_admin = User(
                    shiv_id="SHV-10001",
                    email="admin@shiv.com",
                    username="admin",
                    normalized_username="admin",
                    display_name="SHIV Administrator",
                    role="super_admin",
                    status="active",
                    hashed_password=get_password_hash("shivadmin")
                )
                session.add(new_admin)
                await session.commit()
                admin_id = new_admin.id

            # Backfill legacy projects without owner_id to admin user
            if admin_id:
                try:
                    from app.database.models.project import Project
                    await session.execute(
                        update(Project).where(Project.owner_id.is_(None)).values(owner_id=admin_id)
                    )
                    await session.commit()
                except Exception as ex:
                    logger.warning(f"Could not backfill projects owner_id: {ex}")

        logger.info("Database schema, SHIV Identity models, and admin@shiv.com verified.")
    except Exception as e:
        logger.error(f"Non-fatal warning during startup schema initialization: {e}", exc_info=True)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down SHIV DB & Auth service...")
