"""User / business / officer / admin accounts."""

from typing import List, Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import UserRole, UserStatus
from app.db.base import Base, PublicIdMixin, TimestampMixin


class User(Base, PublicIdMixin, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[str] = mapped_column(String(20), default=UserRole.BUSINESS.value, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE.value, nullable=False)

    # Geographic scope (used by smart assignment: officers matched by district).
    district: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)

    # Business-specific profile attributes (used by the `/business/profile` endpoint).
    business_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    registration_no: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    tax_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Per-user preferences (notifications, theme, 2FA).
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    instruments: Mapped[List["Instrument"]] = relationship(  # noqa: F821
        back_populates="owner", foreign_keys="Instrument.owner_id"
    )
    requests: Mapped[List["VerificationRequest"]] = relationship(  # noqa: F821
        back_populates="applicant", foreign_keys="VerificationRequest.applicant_id"
    )
    assigned_requests: Mapped[List["VerificationRequest"]] = relationship(  # noqa: F821
        back_populates="assigned_officer", foreign_keys="VerificationRequest.assigned_officer_id"
    )
    inspections: Mapped[List["Inspection"]] = relationship(  # noqa: F821
        back_populates="inspector", foreign_keys="Inspection.inspector_id"
    )
    passports: Mapped[List["PassportEvent"]] = relationship(  # noqa: F821
        back_populates="actor", foreign_keys="PassportEvent.actor_id"
    )
    notifications: Mapped[List["Notification"]] = relationship(  # noqa: F821
        back_populates="user",
        foreign_keys="Notification.user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def display_name(self) -> str:
        return self.business_name or self.name