from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.models.base import Base


class GenericRecord(Base):
    __tablename__ = "generic_records"

    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    collection: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    record_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    data_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "collection", "record_id", name="uix_project_collection_record"),
    )
