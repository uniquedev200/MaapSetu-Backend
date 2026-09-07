"""Audit trail for sensitive system events."""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    user_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    action: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)