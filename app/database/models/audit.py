from typing import Optional
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    request_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    project_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    details_json: Mapped[Optional[str]] = mapped_column(Text, default="{}", nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
