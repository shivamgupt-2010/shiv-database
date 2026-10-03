from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class FilterCriterion(BaseModel):
    field: str
    operator: Literal["eq", "neq", "gt", "lt", "gte", "lte", "contains"] = "eq"
    value: Any


class OrderByCriterion(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "asc"


class QueryRequest(BaseModel):
    filters: Optional[List[FilterCriterion]] = Field(default_factory=list)
    order_by: Optional[List[OrderByCriterion]] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class RecordResponse(BaseModel):
    id: str
    collection: str
    data: Dict[str, Any]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
