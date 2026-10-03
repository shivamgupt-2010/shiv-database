import asyncio
import logging
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.base import Base
from app.database.models.project import Project
from app.database.service import DatabaseService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use in-memory SQLite for demo
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Make sure providers_config.json is picked up from correct dir
    # we simulate this by ensuring it's in the current dir for the demo
    
    async with SessionLocal() as db:
        db_service = DatabaseService(db)
        
        # Manually load config for demo script purposes since it might not be in root
        import json
        with open("providers_config.json", "r") as f:
            config = json.load(f)
            db_service.router.load_configuration(config)
        
        logger.info("\n--- SHIV Unified Data Fabric Demonstration ---\n")
        
        # We only need one mock project because all apps share the same data fabric
        mock_project = Project(id="global_fabric", name="SHIV Unified Fabric")
        
        # 1. SHIV Notes app saves a note
        logger.info("SHIV Notes app sends a request to save a note...")
        provider_notes = db_service.get_provider("notes")
        logger.info(f" -> System transparently routed 'notes' to: {provider_notes.__class__.__name__}")
        if hasattr(provider_notes, 'app_name'):
            logger.info(f" -> Physically stored in Firebase App instance: {provider_notes.app_name}")
            
        logger.info("-" * 40)
        
        # 2. SHIV Social Media app saves a post
        logger.info("SHIV Social Media app sends a request to save a post...")
        provider_social = db_service.get_provider("social_posts")
        logger.info(f" -> System transparently routed 'social_posts' to: {provider_social.__class__.__name__}")
        if hasattr(provider_social, 'app_name'):
            logger.info(f" -> Physically stored in Firebase App instance: {provider_social.app_name}")
            
        logger.info("-" * 40)

        # 3. Analytics engine saves metrics
        logger.info("Analytics engine saves log data...")
        provider_analytics = db_service.get_provider("analytics")
        logger.info(f" -> System transparently routed 'analytics' to: {provider_analytics.__class__.__name__}")
        if hasattr(provider_analytics, 'url'):
            logger.info(f" -> Physically stored in Supabase instance: {provider_analytics.url}")

        logger.info("-" * 40)

        # Verify physical isolation of data storage but logical connection for the apps
        assert provider_notes != provider_social, "Storage nodes must be physically separated to maximize free tier!"
        logger.info("SUCCESS: Data is logically unified for the apps, but physically scattered across free-tier providers to save costs.")

if __name__ == "__main__":
    asyncio.run(main())
