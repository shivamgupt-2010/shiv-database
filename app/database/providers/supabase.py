import uuid
from typing import Any, Dict, List, Optional
import httpx
from app.database.providers.base import DatabaseProvider
from app.database.schemas.records import QueryRequest
from app.core.exceptions import ProviderError

class SupabaseDatabaseProvider(DatabaseProvider):
    """Dynamic Supabase database provider for multi-tenancy."""

    def __init__(self, config: dict, project_id: str):
        self.config = config
        self.project_id = project_id
        
        self.url = config.get("url")
        self.api_key = config.get("service_role_key") or config.get("anon_key")
        
        if self.url and self.api_key:
            self.client = httpx.AsyncClient(
                base_url=f"{self.url}/rest/v1",
                headers={
                    "apikey": self.api_key,
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation"
                }
            )
        else:
            self.client = None

    def _check_config(self):
        if not self.client:
            raise ProviderError(f"Supabase is not configured for project {self.project_id}.")

    async def create(
        self,
        project_id: str,
        collection: str,
        data: Dict[str, Any],
        record_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._check_config()
        r_id = record_id or str(uuid.uuid4())
        
        payload = {
            "id": r_id,
            "project_id": project_id,
            "data": data
        }
        
        # We assume there is a generic table called `records` 
        # or that `collection` maps directly to a Supabase table.
        # For a truly multi-tenant generic DB, maybe all go to `shiv_records` table
        # where `collection_name` is a column. Let's use `shiv_records`.
        
        payload["collection_name"] = collection
        
        response = await self.client.post("/shiv_records", json=payload)
        if response.status_code >= 400:
            # If table doesn't exist, we just fail gracefully
            raise ProviderError(f"Supabase create failed: {response.text}")
            
        return response.json()[0]

    async def get(
        self,
        project_id: str,
        collection: str,
        record_id: str,
    ) -> Optional[Dict[str, Any]]:
        self._check_config()
        response = await self.client.get(
            f"/shiv_records?project_id=eq.{project_id}&collection_name=eq.{collection}&id=eq.{record_id}"
        )
        if response.status_code == 200 and len(response.json()) > 0:
            return response.json()[0]
        return None

    async def update(
        self,
        project_id: str,
        collection: str,
        record_id: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        self._check_config()
        # Fetch first to merge `data` JSONB
        existing = await self.get(project_id, collection, record_id)
        if not existing:
            return None
            
        merged_data = existing.get("data", {})
        merged_data.update(data)
        
        response = await self.client.patch(
            f"/shiv_records?project_id=eq.{project_id}&collection_name=eq.{collection}&id=eq.{record_id}",
            json={"data": merged_data}
        )
        if response.status_code >= 400:
            raise ProviderError(f"Supabase update failed: {response.text}")
        return response.json()[0]

    async def delete(
        self,
        project_id: str,
        collection: str,
        record_id: str,
    ) -> bool:
        self._check_config()
        response = await self.client.delete(
            f"/shiv_records?project_id=eq.{project_id}&collection_name=eq.{collection}&id=eq.{record_id}"
        )
        return response.status_code in (200, 204)

    async def query(
        self,
        project_id: str,
        collection: str,
        query_params: QueryRequest,
    ) -> List[Dict[str, Any]]:
        self._check_config()
        
        url = f"/shiv_records?project_id=eq.{project_id}&collection_name=eq.{collection}"
        
        if query_params.filters:
            for f in query_params.filters:
                # map operators to PostgREST syntax
                op_map = {
                    "eq": "eq", "neq": "neq", "gt": "gt", "lt": "lt",
                    "gte": "gte", "lte": "lte", "contains": "cs"
                }
                op = op_map.get(f.operator, "eq")
                
                if isinstance(f.value, str):
                    val = f.value
                else:
                    import json
                    val = json.dumps(f.value)
                
                # Querying inside JSONB column 'data' -> data->>field=eq.value
                url += f"&data->>{f.field}={op}.{val}"
                
        if query_params.order_by:
            ordering = []
            for ob in query_params.order_by:
                ordering.append(f"data->>{ob.field}.{ob.direction}")
            url += f"&order={','.join(ordering)}"
            
        if query_params.limit:
            url += f"&limit={query_params.limit}"
        if query_params.offset:
            url += f"&offset={query_params.offset}"

        response = await self.client.get(url)
        if response.status_code >= 400:
            raise ProviderError(f"Supabase query failed: {response.text}")
            
        return response.json()

    async def health_check(self) -> str:
        if not self.client:
            return "unconfigured"
        try:
            # simple ping
            response = await self.client.get("/shiv_records?limit=1")
            if response.status_code < 500:
                return "healthy"
            return "unhealthy"
        except Exception:
            return "unhealthy"
