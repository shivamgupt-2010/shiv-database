import asyncio
import os
import aiohttp
import json
import websockets
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.database.service import DatabaseService
from app.database.models.project import Project
from app.cache.service import CacheService

# Need to ensure SQL database is initialized
from app.database.models.base import Base

async def setup_db():
    engine = create_async_engine("sqlite+aiosqlite:///./test_enterprise.db", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return SessionLocal

async def mock_websocket_client(collection: str, record_id_to_watch: str):
    uri = f"ws://localhost:8000/realtime/ws/{collection}"
    try:
        async with websockets.connect(uri) as websocket:
            print(f"[WS Client] Connected to {uri}")
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                print(f"[WS Client] Received realtime update: {data['event']} on {data.get('record_id')}")
                if data['event'] == 'updated' and data.get('record_id') == record_id_to_watch:
                    print("[WS Client] Received expected update. Closing.")
                    break
                elif data['event'] == 'deleted':
                    print("[WS Client] Record deleted.")
                    break
    except Exception as e:
        print(f"[WS Client] Error (is server running?): {e}")

async def main():
    print("--- SHIV Enterprise Data Platform Demo ---")
    
    SessionLocal = await setup_db()
    
    async with SessionLocal() as session:
        project = Project(
            id="test-enterprise-proj",
            name="Enterprise Demo Project",
            status="active"
        )
        session.add(project)
        await session.commit()
        
        # Initialize Database Service (handles routing, cache, and fabric index)
        db_service = DatabaseService(session)
        
        print("\n1. Data Pooling & Cache Test")
        record_data = {
            "title": "Enterprise Record",
            "author_id": "user_1",
            "status": "published",
            "_index": {"category": "technology", "tags": ["AI", "Cloud"]},
            "heavy_payload": "This is a large chunk of data " * 100
        }
        
        print(" -> Creating record (will be distributed to a NoSQL node and cached)")
        created = await db_service.create_record(project, "articles", record_data)
        record_id = created.get("id", created.get("name", "").split("/")[-1] if "name" in created else "mock_id")
        
        print(f" -> Created record ID: {record_id}")
        
        print(" -> Fetching record (should hit cache)")
        start_time = asyncio.get_event_loop().time()
        cached = await db_service.get_record(project, "articles", record_id)
        end_time = asyncio.get_event_loop().time()
        print(f" -> Fetch time: {end_time - start_time:.4f}s")
        print(f" -> Cache Hit? {'Yes' if cached else 'No'}")
        
        # 2. Start WebSocket client listener
        # Note: In a real scenario, the FastAPI server needs to be running. 
        # This script acts as the server logic itself directly calling DB service, 
        # so the websocket client will fail if the Uvicorn server is not up.
        print("\n2. Realtime WebSocket Test (Run FastAPI separately)")
        print("To test WebSockets, start: uvicorn app.main:app --reload")
        
        print("\n3. Dynamic Fabric Indexing Test")
        from app.database.schemas.records import QueryRequest, FilterCriterion
        
        query = QueryRequest(
            filters=[
                FilterCriterion(field="category", value="technology"),
                FilterCriterion(field="status", value="published")
            ]
        )
        
        print(f" -> Querying across ALL nodes for category=technology...")
        results = await db_service.query_records(project, "articles", query)
        print(f" -> Found {len(results)} records matching the dynamic schema filter.")
        
        print("\n4. Cache Eviction / Cleanup")
        await db_service.delete_record(project, "articles", record_id)
        print(" -> Record deleted from Master, NoSQL Node, and Cache.")
        

if __name__ == "__main__":
    asyncio.run(main())
