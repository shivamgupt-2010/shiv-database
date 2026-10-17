from sqlalchemy import String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database.models.base import Base


class MediaFile(Base):
    """
    Persistent Native Blob & Media Storage.
    Stores raw files and images securely in the database (Base64) with public CDN-like URLs.
    Zero external dependencies, zero cloud storage costs, no credit card required.
    """
    __tablename__ = "media_files"

    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_base64: Mapped[str] = mapped_column(Text, nullable=False)
