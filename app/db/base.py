"""Declarative base and shared column mixins for SQLAlchemy models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData, String, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    On PostgreSQL the app lives in its own ``metricert`` schema so it never
    collides with the Supabase-managed ``public`` schema that other
    components/tools may already use.
    """

    metadata = MetaData(schema="metricert")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` columns and keeps them up to date."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )


class PublicIdMixin:
    """Public, human-friendly identifier column (e.g. ``INST-2026-8F3A``)."""

    # Populated by id_generator utilities; unique across the table.
    public_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)