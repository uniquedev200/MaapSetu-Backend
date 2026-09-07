"""Inspection service — records and evaluates field inspections."""

from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    InspectionResult,
    InspectionStatus,
    PassportEventType,
    RequestStatus,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.models.inspection import Inspection
from app.models.instrument import Instrument
from app.models.user import User
from app.models.verification_request import VerificationRequest
from app.repositories.inspection_repository import InspectionRepository
from app.schemas.verification import InspectionFindings
from app.services.audit_service import audit
from app.services.passport_service import PassportService
from app.utils import metrology as metrology_util


class InspectionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = InspectionRepository(db)
        self.passport = PassportService(db)

    # ------------------------------------------------------------------
    def get(self, public_id: str) -> Inspection:
        inspection = self.repo.get_by_public_id(public_id)
        if inspection is None:
            raise NotFoundError("Inspection", public_id)
        return inspection

    def list(
        self,
        *,
        user: User,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list, int]:
        """Role-scoped inspection listing."""
        inspector_id = user.id if user.role in ("LMO", "GATC") else None
        owner_id = user.id if user.role == "BUSINESS" else None
        district = user.district if (user.role in ("LMO", "GATC") and user.district) else None
        return self.repo.search(
            page=page, page_size=page_size, search=search, status=status,
            inspector_id=inspector_id, owner_id=owner_id, district=district,
            sort_by=sort_by, sort_order=sort_order,
        )

    def create_scheduled(self, *, request: VerificationRequest, inspector: User,
                         scheduled_date: date, location: Optional[str]) -> Inspection:
        return self.repo.create(
            public_id=self.new_public_id(),
            request_id=request.id,
            instrument_id=request.instrument_id,
            inspector_id=inspector.id,
            status=InspectionStatus.SCHEDULED.value,
            scheduled_date=scheduled_date,
            location=location or request.instrument.installation_location,
        )

    # ------------------------------------------------------------------
    def submit_findings(
        self,
        *,
        request: VerificationRequest,
        officer: User,
        findings: InspectionFindings,
        current_user: User,
    ) -> tuple[Inspection, bool]:
        """Record inspection findings, auto-derive pass/fail and apply lifecycle.

        Returns ``(inspection, passed)``.
        """
        self._assert_can_inspect(request, officer, current_user)

        inspection = self.repo.for_request(request.id)
        if inspection is None:
            inspection = self.repo.create(
                public_id=self.new_public_id(),
                request_id=request.id,
                instrument_id=request.instrument_id,
                inspector_id=officer.id,
                scheduled_date=request.scheduled_date or date.today(),
                location=request.scheduled_location or request.instrument.installation_location,
            )

        # Scientific evaluation of the measurement (OIML R 76-1 / IS 14625).
        # Runs first so an out-of-tolerance reading (even when the officer
        # omitted the toggle) correctly fails the inspection.
        self._apply_metrology_evaluation(inspection, request.instrument, findings)

        passed = self._evaluate(inspection, findings)

        inspection.load_test = findings.load_test
        inspection.eccentricity = findings.eccentricity
        inspection.observations = findings.observations or findings.notes
        inspection.remarks = findings.remarks or findings.notes
        inspection.photos = list(findings.photos or [])
        inspection.inspection_date = date.today()
        request.set_status(RequestStatus.IN_PROGRESS)

        if passed:
            inspection.mark(InspectionStatus.COMPLETED, InspectionResult.PASS)
            self.passport.add_event(
                instrument_id=request.instrument_id,
                event_type=PassportEventType.INSPECTION_PASSED,
                title="Inspection Passed",
                description=f"Field inspection completed successfully by {officer.display_name}",
                metadata={"inspection_id": inspection.public_id},
                actor=officer,
            )
        else:
            inspection.mark(InspectionStatus.FAILED, InspectionResult.FAIL)
            self.passport.add_event(
                instrument_id=request.instrument_id,
                event_type=PassportEventType.INSPECTION_FAILED,
                title="Inspection Failed",
                description=f"Field inspection failed: {(findings.remarks or findings.notes or 'Instrument out of tolerance')[:1000]}",
                metadata={"inspection_id": inspection.public_id},
                actor=officer,
            )

        self.db.add_all([inspection, request])
        self.db.commit()
        self.db.refresh(inspection)

        audit(self.db, user=officer, action="INSPECT", entity_type="inspection", entity_id=inspection.public_id,
              details=f"Inspection result={'PASS' if passed else 'FAIL'} for request {request.public_id}")
        return inspection, passed

    # ------------------------------------------------------------------
    def _assert_can_inspect(self, request: VerificationRequest, officer: User, current_user: User) -> None:
        if request.assigned_officer_id and request.assigned_officer_id != current_user.id and current_user.role != "ADMIN":
            raise ValidationError("This request is assigned to another officer.")
        if not request.assigned_officer_id and current_user.role not in ("ADMIN", "LMO", "GATC"):
            raise ValidationError("Request is not assigned yet. Assign an officer before inspection.")
        if request.status in ("REJECTED", "CANCELLED", "CERTIFICATE_ISSUED"):
            raise ValidationError(f"Cannot inspect a request in status {request.status}.")

    @staticmethod
    def _evaluate(inspection: Inspection, findings: InspectionFindings) -> bool:
        if findings.result:
            value = findings.result.upper()
            if value == "PASS":
                return True
            if value == "FAIL":
                return False
            raise ValidationError("result must be PASS or FAIL")
        return inspection.is_within_tolerance is not False

    @staticmethod
    def _apply_metrology_evaluation(
        inspection: Inspection,
        instrument: Instrument,
        findings: InspectionFindings,
    ) -> None:
        """Compute the OIML R 76-1 / IS 14625 maximum permissible error (MPE)
        for the applied test load and store the deviation alongside the
        reading. Auto-derives the within-tolerance verdict when a nominal
        applied load is supplied."""
        applied = findings.applied_load
        measured = findings.load_test
        explicit = findings.is_within_tolerance
        if applied is None or measured is None:
            if explicit is not None:
                inspection.is_within_tolerance = explicit
            return

        unit = instrument.unit_of_measurement or "kg"
        cls = instrument.accuracy_class or "Class III"
        e = getattr(instrument, "verification_interval_e", None) or metrology_util.e_for(cls, instrument.capacity_max)
        mpe_g, _band_reference = metrology_util.mpe_grams(float(applied), float(e), cls)
        dev_g = metrology_util.deviation_grams(float(measured), float(applied), unit)

        inspection.applied_load = applied
        inspection.deviation_g = round(dev_g, 4)
        inspection.mpe_g = round(mpe_g, 4)
        inspection.metrology_standard = metrology_util.STANDARD_REFERENCE

        within = dev_g <= mpe_g
        # The officer can still deliberately record a failure (e.g. a broken
        # seal or damaged housing) by toggling isWithinTolerance — never the
        # reverse: a bare measurement outside the statutory MPE cannot pass.
        if explicit is False:
            within = False
        inspection.is_within_tolerance = within

    def new_public_id(self) -> str:
        from app.utils.id_generator import inspection_id

        return inspection_id()