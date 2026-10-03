from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.database.schemas.records import QueryRequest


class DatabaseProvider(ABC):
    """Abstract Base Class defining the unified Database Provider interface."""

    @abstractmethod
    async def create(
        self,
        project_id: str,
        collection: str,
        data: Dict[str, Any],
        record_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a record in the target collection."""
        pass

    @abstractmethod
    async def get(
        self,
        project_id: str,
        collection: str,
        record_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a single record by ID."""
        pass

    @abstractmethod
    async def update(
        self,
        project_id: str,
        collection: str,
        record_id: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Update an existing record by ID."""
        pass

    @abstractmethod
    async def delete(
        self,
        project_id: str,
        collection: str,
        record_id: str,
    ) -> bool:
        """Delete a record by ID."""
        pass

    @abstractmethod
    async def query(
        self,
        project_id: str,
        collection: str,
        query_params: QueryRequest,
    ) -> List[Dict[str, Any]]:
        """Query records using structured filters, sorting, and pagination."""
        pass

    @abstractmethod
    async def health_check(self) -> str:
        """Return provider health status ('healthy' or 'unhealthy')."""
        pass
