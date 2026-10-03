import json
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.providers.base import DatabaseProvider
from app.database.models.record import GenericRecord
from app.database.schemas.records import QueryRequest
from app.core.exceptions import ProviderError


class ShivNativeDatabaseProvider(DatabaseProvider):
    """Native database provider using SQLAlchemy and PostgreSQL/SQLite."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: str,
        collection: str,
        data: Dict[str, Any],
        record_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            r_id = record_id or str(uuid.uuid4())
            record = GenericRecord(
                project_id=project_id,
                collection=collection,
                record_id=r_id,
                data_json=json.dumps(data)
            )
            self.session.add(record)
            await self.session.commit()
            await self.session.refresh(record)
            return {
                "id": record.record_id,
                "collection": record.collection,
                "data": json.loads(record.data_json),
                "created_at": record.created_at.isoformat(),
                "updated_at": record.updated_at.isoformat()
            }
        except Exception as e:
            await self.session.rollback()
            raise ProviderError(f"Failed to create record natively: {str(e)}")

    async def get(
        self,
        project_id: str,
        collection: str,
        record_id: str,
    ) -> Optional[Dict[str, Any]]:
        stmt = select(GenericRecord).where(
            GenericRecord.project_id == project_id,
            GenericRecord.collection == collection,
            GenericRecord.record_id == record_id
        )
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        
        if not record:
            return None
            
        return {
            "id": record.record_id,
            "collection": record.collection,
            "data": json.loads(record.data_json),
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat()
        }

    async def update(
        self,
        project_id: str,
        collection: str,
        record_id: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        # Fetch the existing record to merge data, as PATCH is typically partial
        stmt = select(GenericRecord).where(
            GenericRecord.project_id == project_id,
            GenericRecord.collection == collection,
            GenericRecord.record_id == record_id
        )
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        
        if not record:
            return None
            
        try:
            existing_data = json.loads(record.data_json)
            existing_data.update(data)
            
            record.data_json = json.dumps(existing_data)
            await self.session.commit()
            await self.session.refresh(record)
            
            return {
                "id": record.record_id,
                "collection": record.collection,
                "data": json.loads(record.data_json),
                "created_at": record.created_at.isoformat(),
                "updated_at": record.updated_at.isoformat()
            }
        except Exception as e:
            await self.session.rollback()
            raise ProviderError(f"Failed to update record natively: {str(e)}")

    async def delete(
        self,
        project_id: str,
        collection: str,
        record_id: str,
    ) -> bool:
        try:
            stmt = delete(GenericRecord).where(
                GenericRecord.project_id == project_id,
                GenericRecord.collection == collection,
                GenericRecord.record_id == record_id
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            raise ProviderError(f"Failed to delete record natively: {str(e)}")

    async def query(
        self,
        project_id: str,
        collection: str,
        query_params: QueryRequest,
    ) -> List[Dict[str, Any]]:
        # Note: In a production native DB, JSON filtering depends on PostgreSQL JSONB operators.
        # For simplicity and cross-compatibility with SQLite in this example, we retrieve and filter in memory
        # or implement simple textual JSON matching. For a real V1 PostgreSQL deployment, we'd use JSONB operators.
        
        stmt = select(GenericRecord).where(
            GenericRecord.project_id == project_id,
            GenericRecord.collection == collection
        )
        
        # We apply limit and offset, but strictly speaking, if we filter in memory (due to SQLite fallback),
        # we'd need to fetch all and then filter. To keep it simple, let's just fetch all project+collection records
        # and filter in Python for now to guarantee functionality across Postgres & SQLite without complex dialects.
        
        try:
            result = await self.session.execute(stmt)
            records = result.scalars().all()
            
            filtered_results = []
            for record in records:
                data = json.loads(record.data_json)
                match = True
                
                # Apply filters
                if query_params.filters:
                    for f in query_params.filters:
                        val = data.get(f.field)
                        if f.operator == "eq" and not val == f.value: match = False
                        elif f.operator == "neq" and not val != f.value: match = False
                        elif f.operator == "gt" and not (val is not None and val > f.value): match = False
                        elif f.operator == "lt" and not (val is not None and val < f.value): match = False
                        elif f.operator == "gte" and not (val is not None and val >= f.value): match = False
                        elif f.operator == "lte" and not (val is not None and val <= f.value): match = False
                        elif f.operator == "contains" and not (val is not None and f.value in val): match = False
                        
                        if not match:
                            break
                            
                if match:
                    filtered_results.append({
                        "id": record.record_id,
                        "collection": record.collection,
                        "data": data,
                        "created_at": record.created_at.isoformat(),
                        "updated_at": record.updated_at.isoformat()
                    })
                    
            # Apply sorting
            if query_params.order_by:
                for ob in reversed(query_params.order_by): # reverse to apply primary sort last (stable sort)
                    filtered_results.sort(
                        key=lambda x: x["data"].get(ob.field, ""),
                        reverse=(ob.direction == "desc")
                    )
                    
            # Apply pagination
            start = query_params.offset
            end = start + query_params.limit
            return filtered_results[start:end]
            
        except Exception as e:
            raise ProviderError(f"Failed to query records natively: {str(e)}")

    async def health_check(self) -> str:
        try:
            # Simple query to check connection
            await self.session.execute(select(1))
            return "healthy"
        except Exception:
            return "unhealthy"
