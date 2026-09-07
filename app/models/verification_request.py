"""Verification / re-verification requests with full status lifecycle."""

from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import RequestStatus, RequestType
from app.db.base import Base, PublicIdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.instrument import Instrument
    from app.models.inspection import Inspection
    from app.models.certificate import Certificate


class VerificationRequest(Base, PublicIdMixin, TimestampMixin):
    __tablename__ = "verification_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    request_type: Mapped[str] = mapped_column(
        String(32), default=RequestType.NEW_VERIFICATION.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=RequestStatus.SUBMITTED.value, index=True, nullable=False
    )

    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    instrument: Mapped["Instrument"] = relationship(back_populates="requests")

    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    applicant: Mapped["User"] = relationship(back_populates="requests", foreign_keys=[applicant_id])

    # Smart-assignment outputs.
    assigned_officer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    assigned_officer: Mapped[Optional["User"]] = relationship(
        back_populates="assigned_requests", foreign_keys=[assigned_officer_id]
    )
    assigned_entity_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Scheduling.
    preferred_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    scheduled_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    scheduled_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Lifecycle timestamps.
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    inspected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    inspections: Mapped[List["Inspection"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", passive_deletes=True
    )
    certificates: Mapped[List["Certificate"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", passive_deletes=True
    )

    def set_status(self, status: RequestStatus, commit_ts: Optional[datetime] = None) -> None:
        """Advances the request to ``status`` and stamps the matching lifecycle event."""
        ts = commit_ts or datetime.utcnow()
        self.status = status.value
        if status == RequestStatus.SUBMITTED and not self.submitted_at:
            self.submitted_at = ts
        elif status == RequestStatus.APPROVED and not self.approved_at:
            self.approved_at = ts
        elif status == RequestStatus.ASSIGNED_LMO and not self.assigned_at:
            self.assigned_at = ts
        elif status == RequestStatus.SCHEDULED and not self.scheduled_at:
            self.scheduled_at = ts
        elif status == RequestStatus.IN_PROGRESS and not self.inspected_at:
            self.inspected_at = ts
        elif status == RequestStatus.COMPLETED and not self.completed_at:
            self.completed_at = ts
        elif status == RequestStatus.CERTIFICATE_ISSUED and not self.issued_at:
            self.issued_at = ts

    @property
    def type_display(self) -> str:
        try:
            return RequestType(self.request_type).display
        except ValueError:
            return self.request_type