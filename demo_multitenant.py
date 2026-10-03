import asyncio
import json
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.database.models.project import Project
from app.database.routing import ProviderManager
from app.database.service import DatabaseService
from app.core.constants import ProviderTypeEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use in-memory SQLite for demo setup
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def setup_demo_projects():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # 1. SHIV Notes AI -> Uses Firebase Instance 1
        shiv_notes_config = {
            "firebase": {
                "project_id": "shiv-notes-firebase",
                "credentials_json": {} # Mock credentials
            }
        }
        p1 = Project(
            id="proj_notes_123",
            name="SHIV Notes AI",
            primary_provider=ProviderTypeEnum.FIREBASE.value,
            config=json.dumps(shiv_notes_config)
        )

        # 2. SHIV Social Media -> Uses Firebase Instance 2
        shiv_social_config = {
            "firebase": {
                "project_id": "shiv-social-firebase",
                "credentials_json": {} # Mock credentials
            }
        }
        p2 = Project(
            id="proj_social_456",
            name="SHIV Social Media",
            primary_provider=ProviderTypeEnum.FIREBASE.value,
            config=json.dumps(shiv_social_config)
        )

        # 3. SHIV Vision -> Uses Supabase Instance 1
        shiv_vision_config = {
            "supabase": {
                "url": "https://xyz.supabase.co",
                "service_role_key": "mock-admin-key"
            }
        }
        p3 = Project(
            id="proj_vision_789",
            name="SHIV Vision",
            primary_provider=ProviderTypeEnum.SUPABASE.value,
            config=json.dumps(shiv_vision_config)
        )

        db.add_all([p1, p2, p3])
        await db.commit()
        
        return p1, p2, p3

async def main():
    p1, p2, p3 = await setup_demo_projects()

    async with SessionLocal() as db:
        db_service = DatabaseService(db)
        
        logger.info("--- Demonstrating Multi-Tenant Routing ---")
        
        # When a request comes in for SHIV Notes AI:
        provider_1 = await db_service.manager.get_active_provider_for_project(
            primary=p1.primary_provider, project=p1
        )
        logger.info(f"Project '{p1.name}' routed to: {provider_1.__class__.__name__}")
        if hasattr(provider_1, 'app_name'):
            logger.info(f" -> Firebase App Name dynamically isolated to: {provider_1.app_name}")

        # When a request comes in for SHIV Social Media:
        provider_2 = await db_service.manager.get_active_provider_for_project(
            primary=p2.primary_provider, project=p2
        )
        logger.info(f"Project '{p2.name}' routed to: {provider_2.__class__.__name__}")
        if hasattr(provider_2, 'app_name'):
            logger.info(f" -> Firebase App Name dynamically isolated to: {provider_2.app_name}")

        # When a request comes in for SHIV Vision:
        provider_3 = await db_service.manager.get_active_provider_for_project(
            primary=p3.primary_provider, project=p3
        )
        logger.info(f"Project '{p3.name}' routed to: {provider_3.__class__.__name__}")
        if hasattr(provider_3, 'url'):
            logger.info(f" -> Supabase Client URL isolated to: {provider_3.url}")

        logger.info("\nVerify isolation (Are the Firebase providers using the same memory instance?)")
        logger.info(f"Provider 1 ID: {id(provider_1)}")
        logger.info(f"Provider 2 ID: {id(provider_2)}")
        assert id(provider_1) != id(provider_2), "Providers must be isolated instances!"
        logger.info("SUCCESS: Provider instances are dynamically generated and isolated per project.")

if __name__ == "__main__":
    asyncio.run(main())
