"""Field inspection records produced by LMOs / GATCs."""

from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import InspectionResult, InspectionStatus
from app.db.base import Base, PublicIdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.instrument import Instrument
    from app.models.verification_request import VerificationRequest


class Inspection(Base, PublicIdMixin, TimestampMixin):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    request_id: Mapped[int] = mapped_column(
        ForeignKey("verification_requests.id", ondelete="CASCADE"), index=True, nullable=False
    )
    request: Mapped["VerificationRequest"] = relationship(back_populates="inspections")

    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    instrument: Mapped["Instrument"] = relationship()

    inspector_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    inspector: Mapped["User"] = relationship(back_populates="inspections", foreign_keys=[inspector_id])

    status: Mapped[str] = mapped_column(
        String(24), default=InspectionStatus.SCHEDULED.value, index=True, nullable=False
    )
    result: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    inspection_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    scheduled_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    load_test: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eccentricity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_within_tolerance: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photos: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    # Scientific evaluation metadata (OIML R 76-1 / IS 14625).
    applied_load: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deviation_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mpe_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metrology_standard: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    @property
    def location_display(self) -> str:
        return self.location or (self.instrument.installation_location if self.instrument else None) or ""

    def mark(self, status: InspectionStatus, result: Optional[InspectionResult] = None) -> None:
        self.status = status.value
        if result is not None:
            self.result = result.value
        if status in (InspectionStatus.COMPLETED, InspectionStatus.FAILED):
            self.completed_at = datetime.utcnow()