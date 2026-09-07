"""Instrument registration & lifecycle service."""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import InstrumentStatus, PassportEventType
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.instrument import Instrument
from app.models.user import User
from app.repositories.instrument_repository import InstrumentRepository
from app.services.audit_service import audit
from app.services.health_score_service import HealthScoreService
from app.services.passport_service import PassportService
from app.services.storage_service import storage_service
from app.utils.id_generator import instrument_id


class InstrumentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InstrumentRepository(db)
        self.passport = PassportService(db)
        self.health = HealthScoreService(db)

    # ------------------------------------------------------------------
    def create(self, *, user: User, data, photo_bytes: Optional[bytes] = None, photo_name: Optional[str] = None) -> Instrument:
        if self.repo.get_by_serial(data.serial_number):
            raise ConflictError("An instrument with this serial number is already registered.")

        photo_url = None
        if photo_bytes and len(photo_bytes) > 0:
            path = storage_service.upload(
                folder="instruments",
                filename=storage_service.make_filename(photo_name or "photo.jpg"),
                content=photo_bytes,
            )
            photo_url = storage_service.public_url(path)

        instrument = self.repo.create(
            public_id=instrument_id(),
            name=data.name,
            instrument_type=data.instrument_type,
            manufacturer=data.manufacturer,
            model_number=data.model_number,
            serial_number=data.serial_number,
            capacity_max=data.capacity_max,
            capacity_min=data.capacity_min,
            unit_of_measurement=data.unit_of_measurement,
            accuracy_class=data.accuracy_class,
            verification_interval_e=data.verification_interval_e,
            installation_location=data.installation_location,
            district=data.district,
            installed_at=data.installed_at,
            status=InstrumentStatus.REGISTERED.value,
            verification_frequency_months=data.verification_frequency_months,
            health_score=100,
            owner_id=user.id,
            photo_url=photo_url,
        )

        self.passport.add_event(
            instrument_id=instrument.id,
            event_type=PassportEventType.REGISTERED,
            title="Instrument Registered",
            description=f"{instrument.name} ({instrument.serial_number}) registered to {user.display_name}",
            metadata={"instrument_id": instrument.public_id, "serial_number": instrument.serial_number},
            actor=user,
        )
        self.health.recalculate(instrument, reason="Initial registration")
        audit(self.db, user=user, action="CREATE", entity_type="instrument", entity_id=instrument.public_id,
              details=f"Registered instrument {instrument.name} ({instrument.serial_number})")
        return instrument

    def register_complaint(self, *, instrument: Instrument, user: User, description: str, severity: str = "MINOR") -> Instrument:
        if instrument.owner_id != user.id and user.role != "ADMIN":
            raise ValidationError("Only the owning business or an admin can log a complaint.")
        self.passport.add_event(
            instrument_id=instrument.id,
            event_type=PassportEventType.COMPLAINT,
            title="Complaint Registered",
            description=description,
            metadata={"severity": severity},
            actor=user,
        )
        self.health.recalculate(instrument, reason="Complaint logged")
        audit(self.db, user=user, action="CREATE", entity_type="instrument", entity_id=instrument.public_id,
              details=f"Complaint logged: {description[:200]}")
        return instrument

    def get_for_user(self, instrument: Instrument, user: User) -> Instrument:
        self._assert_access(instrument, user)
        return instrument

    def get_by_public_id(self, public_id: str, *, current_user: Optional[User] = None) -> Instrument:
        from app.core.exceptions import NotFoundError

        instrument = self.repo.get_by_public_id(public_id)
        if instrument is None:
            raise NotFoundError("Instrument", public_id)
        if current_user is not None:
            self._assert_access(instrument, current_user)
        return instrument

    def attach_photo(self, *, public_id: str, path: str) -> Instrument:
        instrument = self.get_by_public_id(public_id)
        from app.core.config import get_settings

        instrument.photo_url = storage_service.public_url(path)
        self.repo.save(instrument)
        return instrument

    def update(self, *, instrument: Instrument, user: User, data, **fields) -> Instrument:
        self._assert_access(instrument, user)
        updates = {}
        if data:
            for key in ("name", "instrument_type", "manufacturer", "model_number", "capacity_max",
                        "capacity_min", "unit_of_measurement", "accuracy_class", "verification_interval_e",
                        "installation_location", "district", "verification_frequency_months"):
                value = getattr(data, key, None)
                if value is not None:
                    updates[key] = value
        updates.update(fields)
        if "status" in updates:
            self._assert_status_transition(instrument, updates["status"])
        instrument = self.repo.update(instrument, **updates)
        audit(self.db, user=user, action="UPDATE", entity_type="instrument", entity_id=instrument.public_id,
              details="Instrument details updated")
        return instrument

    def delete(self, *, instrument: Instrument, user: User) -> None:
        self._assert_access(instrument, user)
        if instrument.requests and any(r.status not in ("CANCELLED", "REJECTED", "CERTIFICATE_ISSUED") for r in instrument.requests):
            raise ValidationError("Cannot delete an instrument with active verification requests.")
        audit(self.db, user=user, action="DELETE", entity_type="instrument", entity_id=instrument.public_id,
              details=f"Deleted instrument {instrument.public_id}")
        self.repo.delete(instrument)

    def list(
        self,
        *,
        user: User,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        instrument_type: Optional[str] = None,
        district: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list, int]:
        owner_id = user.id if user.role == "BUSINESS" else None
        officer_id = user.id if user.role in ("LMO", "GATC") else None
        # Officers are already scoped to their assigned/performed instruments by
        # the repo (authoritative). Do not auto-default a district filter for
        # them here, otherwise assigned instruments whose district is unset or
        # outside the officer's district get hidden.
        district_param = district
        return self.repo.search(
            page=page, page_size=page_size, search=search, status=status,
            instrument_type=instrument_type, district=district_param, owner_id=owner_id,
            officer_id=officer_id,
            sort_by=sort_by, sort_order=sort_order,
        )

    # ------------------------------------------------------------------
    def _assert_access(self, instrument: Instrument, user: User) -> None:
        if user.role != "ADMIN" and instrument.owner_id != user.id:
            raise ValidationError("You do not have access to this instrument.")

    def _assert_status_transition(self, instrument: Instrument, new_status: str) -> None:
        valid = [s.value for s in InstrumentStatus]
        if new_status not in valid:
            raise ValidationError(f"Invalid instrument status: {new_status}")