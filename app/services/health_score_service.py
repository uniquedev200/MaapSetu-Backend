"""Instrument health scoring service.

Score starts at 100 and is **recomputed from facts** every time a lifecycle
event occurs (inspections, complaints, age, overdue), then clamped 0–100.
"""

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import HealthCategory, InspectionResult, PassportEventType
from app.models.certificate import Certificate
from app.models.health_score import HealthScore
from app.models.inspection import Inspection
from app.models.instrument import Instrument
from app.models.passport_event import PassportEvent
from app.repositories.certificate_repository import CertificateRepository
from app.repositories.health_repository import HealthScoreRepository
from app.repositories.inspection_repository import InspectionRepository
from app.repositories.passport_repository import PassportRepository


def category_for(score: int) -> HealthCategory:
    if score >= 90:
        return HealthCategory.EXCELLENT
    if score >= 70:
        return HealthCategory.GOOD
    if score >= 50:
        return HealthCategory.NEEDS_ATTENTION
    return HealthCategory.CRITICAL


class HealthScoreService:
    """Computes and persists instrument health scores."""

    def __init__(self, db: Session):
        self.db = db
        self.health_repo = HealthScoreRepository(db)
        self.insp_repo = InspectionRepository(db)
        self.cert_repo = CertificateRepository(db)
        self.passport_repo = PassportRepository(db)

    # ------------------------------------------------------------------
    def recalculate(self, instrument: Instrument, reason: str = "Lifecycle event") -> HealthScore:
        """Recompute the instrument score from audit facts and persist a snapshot."""
        instrument_id = instrument.id
        inspections: list[Inspection] = [
            i for i in self.insp_repo.query(Inspection.instrument_id == instrument_id)
        ]
        passed = sum(1 for i in inspections if i.result == InspectionResult.PASS.value)
        failed = sum(1 for i in inspections if i.result == InspectionResult.FAIL.value)

        complaints = 0
        for event in self.passport_repo.for_instrument(instrument_id):
            if event.event_type == PassportEventType.COMPLAINT.value:
                complaints += 1

        age_deduction = int(instrument.age_years) * 2

        if self._is_overdue(instrument):
            overdue_deduction = 5
        else:
            overdue_deduction = 0

        score = 100 + (passed * 5) - (failed * 10) - (complaints * 5) - age_deduction - overdue_deduction
        score = max(0, min(100, score))

        category = category_for(score).value
        snapshot = self.health_repo.create(
            instrument_id=instrument.id,
            score=score,
            category=category,
            reason=f"{reason} (passed={passed}, failed={failed}, complaints={complaints}, age_deduction={age_deduction}, overdue={overdue_deduction})",
        )

        instrument.health_score = score
        self.db.add(instrument)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def latest(self, instrument_id: int) -> Optional[HealthScore]:
        return self.health_repo.latest_for(instrument_id)

    def history(self, instrument_id: int, limit: int = 20) -> list[HealthScore]:
        return self.health_repo.history_for(instrument_id, limit=limit)

    # ------------------------------------------------------------------
    def _is_overdue(self, instrument: Instrument) -> bool:
        from app.repositories.verification_repository import VerificationRepository

        active_request = VerificationRepository(self.db).first_active_for_instrument(instrument.id)
        if active_request is not None:
            return False

        latest_cert: Optional[Certificate] = None
        certs = self.cert_repo.query(Certificate.instrument_id == instrument.id)
        if certs:
            latest_cert = max(certs, key=lambda c: c.issued_date)

        if latest_cert is None:
            # Never verified; overdue once instrument has been around >= its frequency window.
            freq = instrument.verification_frequency_months
            installed = instrument.installed_at or (instrument.created_at.date() if hasattr(instrument.created_at, "date") else date.today())
            age_days = (date.today() - installed).days
            return age_days >= freq * 30

        return latest_cert.expiry_date < date.today()