from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.sql import func
from app.database.models.base import Base

class FabricIndex(Base):
    """
    Master Index for the True Data Pooling System.
    This tracks which physical database node every single record lives on,
    as well as searchable fields for fast scatter-gather querying.
    """
    __tablename__ = "fabric_index"

    id = Column(String, primary_key=True, index=True) # The universal record ID
    collection_name = Column(String, index=True, nullable=False) # e.g. 'notes'
    node_id = Column(String, nullable=False) # e.g. 'firebase_1'
    
    # Searchable Summary Fields (Stored in SQL for fast querying)
    title = Column(String, index=True, nullable=True)
    author_id = Column(String, index=True, nullable=True)
    status = Column(String, index=True, nullable=True)
    
    # Enterprise dynamic indexing
    indexed_data = Column(JSON, nullable=True, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
