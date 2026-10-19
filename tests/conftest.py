import os
import sys
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure repository root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.main import app as fastapi_app, startup_event
from app.database.models.base import Base
from app.database.session import get_db_session as get_db
import app.database.models.auth
import app.database.models.project
import app.database.models.record
import app.database.models.audit
import app.database.models.fabric
import app.database.models.media
import app.database.models.oauth

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


fastapi_app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Explicitly seed admin user in in-memory test database
    from app.database.models.auth import User
    from app.auth.password import get_password_hash
    async with TestingSessionLocal() as session:
        admin_user = User(
            shiv_id="SHV-10001",
            email="admin@shiv.com",
            username="admin",
            normalized_username="admin",
            display_name="SHIV Administrator",
            role="super_admin",
            status="active",
            hashed_password=get_password_hash("shivadmin")
        )
        session.add(admin_user)
        await session.commit()

    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac
