"""Registered weighing / measuring instruments."""

from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, Float, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import InstrumentStatus
from app.db.base import Base, PublicIdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.verification_request import VerificationRequest
    from app.models.health_score import HealthScore
    from app.models.passport_event import PassportEvent


class Instrument(Base, PublicIdMixin, TimestampMixin):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Public instrument id (e.g. INST-2026-4F2A) — "Instrument ID" per spec.
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    model_number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    serial_number: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    capacity_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capacity_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit_of_measurement: Mapped[str] = mapped_column(String(20), default="kg", nullable=False)
    accuracy_class: Mapped[Optional[str]] = mapped_column(String(40), default="Class III", nullable=True)
    # Verification scale interval ``e`` (grams) used for OIML R 76-1 / IS 14625 MPE checks.
    verification_interval_e: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    installation_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    installed_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), default=InstrumentStatus.REGISTERED.value, index=True, nullable=False
    )
    verification_frequency_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)

    # Cache of the latest computed health score (0-100) for cheap reads.
    health_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    owner: Mapped["User"] = relationship(back_populates="instruments", foreign_keys=[owner_id])

    requests: Mapped[List["VerificationRequest"]] = relationship(
        back_populates="instrument", passive_deletes=True
    )
    health_scores: Mapped[List["HealthScore"]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan", passive_deletes=True
    )
    passport_events: Mapped[List["PassportEvent"]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan", passive_deletes=True, order_by="PassportEvent.created_at"
    )

    @property
    def age_years(self) -> float:
        if not self.installed_at:
            return 0.0
        return max(0.0, (date.today() - self.installed_at).days / 365.25)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Instrument {self.public_id} {self.serial_number}>"