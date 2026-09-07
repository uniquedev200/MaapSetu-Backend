"""Digital Instrument Passport service — immutable lifecycle timeline."""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.enums import PassportEventType
from app.models.passport_event import PassportEvent
from app.models.user import User
from app.repositories.passport_repository import PassportRepository


class PassportService:
    """Appends immutable lifecycle events to an instrument's digital passport."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = PassportRepository(db)

    def add_event(
        self,
        *,
        instrument_id: int,
        event_type: str | PassportEventType,
        title: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        actor: Optional[User] = None,
    ) -> PassportEvent:
        type_value = event_type.value if isinstance(event_type, PassportEventType) else event_type
        return self.repo.create(
            instrument_id=instrument_id,
            event_type=type_value,
            title=title,
            description=description,
            metadata_json=metadata or {},
            actor_id=actor.id if actor else None,
        )

    def timeline(self, instrument_id: int) -> list[PassportEvent]:
        return self.repo.for_instrument(instrument_id)

    def build_passport(self, instrument: Any) -> Dict[str, Any]:
        """Assemble the full passport payload for ``GET /instruments/{id}/passport``."""
        from app.repositories.certificate_repository import CertificateRepository
        from app.repositories.inspection_repository import InspectionRepository
        from app.repositories.health_repository import HealthScoreRepository
        from app.repositories.verification_repository import VerificationRepository

        inspections = InspectionRepository(self.db).query(
            InspectionRepository.model.instrument_id == instrument.id
        )
        certificates = CertificateRepository(self.db).query(
            CertificateRepository.model.instrument_id == instrument.id
        )
        requests = VerificationRepository(self.db).query(
            VerificationRepository.model.instrument_id == instrument.id
        )
        latest_health = HealthScoreRepository(self.db).latest_for(instrument.id)

        active_cert = next(
            (c for c in sorted(certificates, key=lambda c: c.issued_date, reverse=True)
             if c.status == "ACTIVE"),
            None,
        )
        verification_summary = {
            "total_verifications": len(inspections),
            "passed": sum(1 for i in inspections if i.result == "PASS"),
            "failed": sum(1 for i in inspections if i.result == "FAIL"),
            "total_certificates": len(certificates),
            "active_certificate": (
                {
                    "id": c.public_id,
                    "issued_date": c.issued_date.isoformat(),
                    "expiry_date": c.expiry_date.isoformat(),
                    "status": c.status,
                    "certificate_hash": c.certificate_hash,
                    "block_index": c.block_index,
                }
                if (c := active_cert)
                else None
            ),
            "total_requests": len(requests),
        }

        timeline = []
        for event in self.repo.for_instrument(instrument.id):
            timeline.append(
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "title": event.title,
                    "description": event.description,
                    "metadata": event.metadata_json,
                    "actor": event.actor.display_name if event.actor else None,
                    "created_at": event.created_at.isoformat(),
                }
            )

        health_score = instrument.health_score
        from app.services.health_score_service import category_for

        health_category = category_for(health_score).value
        if latest_health is not None:
            health_category = latest_health.category

        return {
            "instrument": {
                "id": instrument.public_id,
                "name": instrument.name,
                "serial_number": instrument.serial_number,
                "instrument_type": instrument.instrument_type,
                "manufacturer": instrument.manufacturer,
                "model_number": instrument.model_number,
                "capacity_max": instrument.capacity_max,
                "unit_of_measurement": instrument.unit_of_measurement,
                "accuracy_class": instrument.accuracy_class,
                "installation_location": instrument.installation_location,
                "district": instrument.district,
                "installed_at": instrument.installed_at.isoformat() if instrument.installed_at else None,
                "status": instrument.status,
            },
            "health_score": health_score,
            "health_category": health_category,
            "health_history": [
                {"score": h.score, "category": h.category, "reason": h.reason,
                 "computed_at": h.computed_at.isoformat()}
                for h in HealthScoreRepository(self.db).history_for(instrument.id, limit=20)
            ],
            "verification_summary": verification_summary,
            "timeline": timeline,
        }