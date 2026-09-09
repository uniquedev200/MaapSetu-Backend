"""In-app user notifications driven by verification workflow events."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Recipient — every role (BUSINESS / LMO / GATC / ADMIN) has a feed.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user: Mapped["User"] = relationship(back_populates="notifications", foreign_keys=[user_id])

    # Who triggered the event (applicant / officer / admin). Null for system events.
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor: Mapped[Optional["User"]] = relationship(foreign_keys=[actor_id])

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Machine-readable category, e.g. REQUEST_SUBMITTED / INSPECTION_SCHEDULED.
    type: Mapped[str] = mapped_column(String(64), default="SYSTEM", nullable=False, index=True)

    # Frontend deep link (e.g. "/applications/VR-2026-XYZ").
    link: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Optional structured payload (request / certificate metadata).
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def mark_read(self) -> None:
        self.is_read = True
        self.read_at = utcnow()