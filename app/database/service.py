import json
import os
import uuid
import asyncio
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update, func
from app.database.routing import PoolRouter
from app.database.schemas.records import QueryRequest
from app.database.models.project import Project
from app.database.models.fabric import FabricIndex
from app.cache.service import CacheService
from app.api.routes.realtime import manager as realtime_manager

class DatabaseService:
    """High-level service coordinating the True Data Pooling System."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.router = PoolRouter(session)
        self.cache = CacheService()
        
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "providers_config.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                    self.router.load_configuration(config)
        except Exception as e:
            import logging
            logging.error(f"Could not load providers_config.json: {e}")

    async def create_record(
        self, project: Project, collection: str, data: Dict[str, Any], record_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not record_id:
            record_id = str(uuid.uuid4())

        provider, node_id = self.router.get_provider_for_new_record()
        
        # Extract dynamic indexing
        indexed_data = data.pop("_index", {})
        
        # Save pointer and searchable data to SQL Master Node
        fabric_record = FabricIndex(
            id=record_id,
            collection_name=collection,
            node_id=node_id,
            title=data.get("title"),
            author_id=data.get("author_id"),
            status=data.get("status"),
            indexed_data=indexed_data
        )
        self.session.add(fabric_record)
        await self.session.commit()

        # Save heavy payload to distributed NoSQL Node
        saved_data = await provider.create(project.id, collection, data, record_id)
        
        # Update Cache and Notify WebSockets
        if saved_data:
            await self.cache.set_record(collection, record_id, saved_data)
            asyncio.create_task(realtime_manager.broadcast_update(collection, record_id, {"event": "created", "data": saved_data}))
            
        return saved_data

    async def get_record(
        self, project: Project, collection: str, record_id: str
    ) -> Optional[Dict[str, Any]]:
        # 1. Check Cache first (Lightning fast Redis)
        cached_data = await self.cache.get_record(collection, record_id)
        if cached_data:
            return cached_data
            
        # 2. Find which node has the data
        result = await self.session.execute(select(FabricIndex).where(FabricIndex.id == record_id))
        fabric_record = result.scalars().first()
        if not fabric_record:
            return None
            
        provider = self.router.get_provider_by_id(fabric_record.node_id)
        data = await provider.get(project.id, collection, record_id)
        
        # 3. Save to cache
        if data:
            await self.cache.set_record(collection, record_id, data)
            
        return data

    async def update_record(
        self, project: Project, collection: str, record_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        result = await self.session.execute(select(FabricIndex).where(FabricIndex.id == record_id))
        fabric_record = result.scalars().first()
        if not fabric_record:
            return None
            
        # Update summary in SQL
        needs_commit = False
        if any(k in data for k in ["title", "author_id", "status"]):
            if "title" in data: fabric_record.title = data["title"]
            if "author_id" in data: fabric_record.author_id = data["author_id"]
            if "status" in data: fabric_record.status = data["status"]
            needs_commit = True
            
        if "_index" in data:
            fabric_record.indexed_data = {**fabric_record.indexed_data, **data.pop("_index")}
            needs_commit = True
            
        if needs_commit:
            await self.session.commit()
            
        provider = self.router.get_provider_by_id(fabric_record.node_id)
        updated_data = await provider.update(project.id, collection, record_id, data)
        
        if updated_data:
            await self.cache.set_record(collection, record_id, updated_data)
            asyncio.create_task(realtime_manager.broadcast_update(collection, record_id, {"event": "updated", "data": updated_data}))
            
        return updated_data

    async def delete_record(
        self, project: Project, collection: str, record_id: str
    ) -> bool:
        result = await self.session.execute(select(FabricIndex).where(FabricIndex.id == record_id))
        fabric_record = result.scalars().first()
        if not fabric_record:
            return False
            
        provider = self.router.get_provider_by_id(fabric_record.node_id)
        
        # Delete from Master
        await self.session.delete(fabric_record)
        await self.session.commit()
        
        # Delete from Cache
        await self.cache.invalidate_record(collection, record_id)
        
        # Notify WebSockets
        asyncio.create_task(realtime_manager.broadcast_update(collection, record_id, {"event": "deleted"}))
        
        # Delete from physical node
        return await provider.delete(project.id, collection, record_id)

    async def query_records(
        self, project: Project, collection: str, query_params: QueryRequest
    ) -> List[Dict[str, Any]]:
        # Use SQL to search quickly across ALL instances simultaneously
        stmt = select(FabricIndex).where(FabricIndex.collection_name == collection)
        
        # Basic filtering on searchable fields
        for filter_item in query_params.filters or []:
            if filter_item.field == "title":
                stmt = stmt.where(FabricIndex.title == filter_item.value)
            elif filter_item.field == "author_id":
                stmt = stmt.where(FabricIndex.author_id == filter_item.value)
            elif filter_item.field == "status":
                stmt = stmt.where(FabricIndex.status == filter_item.value)
            else:
                # Dynamic JSON filtering (SQLite json_extract compatible)
                stmt = stmt.where(func.json_extract(FabricIndex.indexed_data, f"$.{filter_item.field}") == filter_item.value)
                
        if query_params.limit:
            stmt = stmt.limit(query_params.limit)
            
        result = await self.session.execute(stmt)
        fabric_records = result.scalars().all()
        
        if not fabric_records:
            return []
            
        # Scatter-gather fetch of full payloads
        tasks = []
        for record in fabric_records:
            # Check cache first for each record in the scatter gather!
            tasks.append(self._get_record_cached(project.id, collection, record))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [res for res in results if res and not isinstance(res, Exception)]
        
    async def _get_record_cached(self, project_id, collection, record: FabricIndex):
        cached = await self.cache.get_record(collection, record.id)
        if cached: return cached
        provider = self.router.get_provider_by_id(record.node_id)
        data = await provider.get(project_id, collection, record.id)
        if data:
            await self.cache.set_record(collection, record.id, data)
        return data

    async def health_check_providers(self) -> Dict[str, str]:
        return await self.router.health_check_all()
