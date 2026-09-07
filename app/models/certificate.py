"""Digital verification certificates with blockchain anchoring metadata."""

from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import CertificateStatus
from app.db.base import Base, PublicIdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.instrument import Instrument
    from app.models.verification_request import VerificationRequest


class Certificate(Base, PublicIdMixin, TimestampMixin):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    certificate_number: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)

    request_id: Mapped[int] = mapped_column(
        ForeignKey("verification_requests.id", ondelete="CASCADE"), index=True, nullable=False
    )
    request: Mapped["VerificationRequest"] = relationship(back_populates="certificates")

    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    instrument: Mapped["Instrument"] = relationship()

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])

    inspector_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    inspector: Mapped[Optional["User"]] = relationship(foreign_keys=[inspector_id])

    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=CertificateStatus.ACTIVE.value, index=True, nullable=False
    )

    pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    qr_code_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    certificate_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Blockchain anchoring (populated by BlockchainService at issuance time).
    block_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    block_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    verification_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Demo tamper-simulation bookkeeping. When ``is_tampered`` is True the
    # stored hash/artefacts no longer match the anchored blockchain block and
    # public verification MUST fail — exactly what a real forgery looks like.
    is_tampered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tamper_meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)