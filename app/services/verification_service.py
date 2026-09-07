"""Verification request lifecycle service (submission → certificate / reject)."""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    InstrumentStatus,
    PassportEventType,
    RequestStatus,
    UserRole,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.certificate import Certificate
from app.models.instrument import Instrument
from app.models.user import User
from app.models.verification_request import VerificationRequest
from app.repositories.instrument_repository import InstrumentRepository
from app.repositories.verification_repository import VerificationRepository
from app.schemas.verification import InspectionFindings, VerificationRequestCreate
from app.services.assignment_service import AssignmentService
from app.services.audit_service import audit
from app.services.certificate_service import CertificateService
from app.services.health_score_service import HealthScoreService
from app.services.inspection_service import InspectionService
from app.services.passport_service import PassportService
from app.utils.id_generator import request_id


class VerificationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = VerificationRepository(db)
        self.instruments = InstrumentRepository(db)
        self.passport = PassportService(db)
        self.assignment = AssignmentService(db)
        self.inspections = InspectionService(db)
        self.certificates = CertificateService(db)
        self.health = HealthScoreService(db)

    # ------------------------------------------------------------------
    def create(self, *, user: User, data: VerificationRequestCreate) -> VerificationRequest:
        instrument = self._resolve_instrument(data, user)

        existing = self.repo.first_active_for_instrument(instrument.id)
        if existing is not None:
            raise ConflictError(
                f"Instrument {instrument.serial_number} already has an active request ({existing.public_id})."
            )

        req = self.repo.create(
            public_id=request_id(),
            request_type=data.request_type.value,
            status=RequestStatus.DRAFT.value,
            instrument_id=instrument.id,
            applicant_id=user.id,
            preferred_date=data.preferred_date,
            remarks=data.remarks,
        )

        if data.submit_now:
            req = self.submit(req, user)

        audit(self.db, user=user, action="CREATE", entity_type="verification_request",
              entity_id=req.public_id, details=f"Created verification request for {instrument.serial_number}")
        return req

    def update(self, req: VerificationRequest, user: User, data) -> VerificationRequest:
        """Edit editable fields of a DRAFT (or REJECTED, for resubmission) request."""
        self._assert_owner(req, user)
        if req.status not in (RequestStatus.DRAFT.value, RequestStatus.REJECTED.value):
            raise ValidationError(
                f"Cannot edit a request in status {req.status}."
            )
        device = {}
        for key in ("request_type", "preferred_date", "remarks"):
            value = getattr(data, key, None)
            if value is not None:
                device[key] = value.value if hasattr(value, "value") else value
        if device:
            req = self.repo.update(req, **device)
        return req

    def submit(self, req: VerificationRequest, user: User) -> VerificationRequest:
        self._assert_owner(req, user)
        if req.status not in (RequestStatus.DRAFT.value, RequestStatus.REJECTED.value):
            raise ValidationError(f"Cannot submit a request in status {req.status}.")

        req.set_status(RequestStatus.SUBMITTED)
        req.instrument.status = InstrumentStatus.PENDING_VERIFICATION.value
        self.db.add_all([req, req.instrument])
        self.db.commit()
        self.db.refresh(req)

        self.passport.add_event(
            instrument_id=req.instrument_id,
            event_type=PassportEventType.VERIFICATION_REQUESTED,
            title="Verification Requested",
            description=f"{req.type_display} request submitted ({req.public_id})",
            metadata={"request_id": req.public_id, "type": req.type_display},
            actor=user,
        )
        return req

    def approve_and_assign(self, req: VerificationRequest, admin: User,
                           officer_id: Optional[int] = None,
                           entity_type: Optional[str] = None,
                           strategy: str = "auto") -> VerificationRequest:
        """Admin approval → automatic smart assignment to LMO/GATC."""
        if req.status not in (RequestStatus.SUBMITTED.value, RequestStatus.APPROVED.value):
            raise ValidationError(f"Cannot approve a request in status {req.status}.")
        if admin.role != UserRole.ADMIN.value:
            raise ValidationError("Only an admin can approve requests.")

        req.set_status(RequestStatus.APPROVED)
        self.passport.add_event(
            instrument_id=req.instrument_id,
            event_type=PassportEventType.REQUEST_APPROVED,
            title="Request Approved",
            description=f"Verification request {req.public_id} approved",
            metadata={"request_id": req.public_id},
            actor=admin,
        )

        officer, entity = self.assignment.assign(
            req, officer_id=officer_id, entity_type=entity_type, strategy=strategy
        )
        req.set_status(RequestStatus.ASSIGNED_LMO)
        req.instrument.status = InstrumentStatus.UNDER_VERIFICATION.value
        self.db.add_all([req, req.instrument])
        self.db.commit()
        self.db.refresh(req)

        self.passport.add_event(
            instrument_id=req.instrument_id,
            event_type=PassportEventType.ASSIGNED,
            title="Officer Assigned",
            description=f"Assigned to {officer.display_name} ({entity})",
            metadata={"request_id": req.public_id, "officer": officer.public_id},
            actor=admin,
        )
        audit(self.db, user=admin, action="ASSIGN", entity_type="verification_request",
              entity_id=req.public_id, details=f"Assigned request to {officer.display_name} ({entity})")
        return req

    def assign_manual(self, req: VerificationRequest, admin: User, officer_id: int) -> VerificationRequest:
        return self.approve_and_assign(
            req, admin, officer_id=officer_id, strategy="manual"
        ) if req.status == RequestStatus.APPROVED.value else self._assign_only(req, admin, officer_id)

    def _assign_only(self, req: VerificationRequest, admin: User, officer_id: int) -> VerificationRequest:
        if req.status not in (RequestStatus.APPROVED.value, RequestStatus.ASSIGNED_LMO.value):
            raise ValidationError("Request must be approved before assignment.")
        officer, entity = self.assignment.assign(req, officer_id=officer_id, strategy="manual")
        req.set_status(RequestStatus.ASSIGNED_LMO)
        req.instrument.status = InstrumentStatus.UNDER_VERIFICATION.value
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)
        return req

    def schedule(self, req: VerificationRequest, officer: User, scheduled_date, scheduled_location=None) -> VerificationRequest:
        self._assert_officer(req, officer)
        if req.status not in (RequestStatus.ASSIGNED_LMO.value, RequestStatus.SCHEDULED.value, RequestStatus.IN_PROGRESS.value):
            raise ValidationError(f"Cannot schedule a request in status {req.status}.")

        req.scheduled_date = scheduled_date
        req.scheduled_location = scheduled_location
        req.set_status(RequestStatus.SCHEDULED)
        self.inspections.create_scheduled(
            request=req,
            inspector=req.assigned_officer or officer,
            scheduled_date=scheduled_date,
            location=scheduled_location,
        )
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)

        self.passport.add_event(
            instrument_id=req.instrument_id,
            event_type=PassportEventType.INSPECTION_SCHEDULED,
            title="Inspection Scheduled",
            description=f"Inspection scheduled for {scheduled_date.isoformat()} at {scheduled_location or 'installation site'}",
            metadata={"request_id": req.public_id, "date": scheduled_date.isoformat()},
            actor=officer,
        )
        return req

    def inspect(self, req: VerificationRequest, user: User, findings: InspectionFindings) -> dict:
        """Officer submits inspection findings for the request."""
        officer = user if user.role in (UserRole.LMO.value, UserRole.GATC.value, UserRole.ADMIN.value) else None
        if officer is None:
            raise ValidationError("Only LMO/GATC officers can submit inspection findings.")

        inspection, passed = self.inspections.submit_findings(
            request=req, officer=officer, findings=findings, current_user=user
        )

        if passed:
            req.set_status(RequestStatus.COMPLETED)
            self.db.add(req)
            self.db.commit()
            cert = self.certificates.issue(request=req, inspector=officer)
            self.health.recalculate(req.instrument, reason="Successful verification")
            return {"passed": True, "inspection": inspection.public_id, "certificate": cert.public_id,
                    "status": req.status}

        req.set_status(RequestStatus.REJECTED)
        req.rejection_reason = (findings.remarks or findings.observations or "Instrument failed verification inspection")
        req.instrument.status = InstrumentStatus.FAILED.value
        self.db.add_all([req, req.instrument])
        self.db.commit()
        self.health.recalculate(req.instrument, reason="Failed verification")
        return {"passed": False, "inspection": inspection.public_id, "status": req.status,
                "reason": req.rejection_reason}

    def cancel(self, req: VerificationRequest, user: User) -> VerificationRequest:
        if req.status in ("CANCELLED", "REJECTED", "CERTIFICATE_ISSUED"):
            raise ValidationError(f"Cannot cancel a request in status {req.status}.")
        if user.role != "ADMIN" and req.applicant_id != user.id and req.assigned_officer_id != user.id:
            raise ValidationError("You cannot cancel this request.")
        req.set_status(RequestStatus.CANCELLED)
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)
        return req

    # ------------------------------------------------------------------
    def list(
        self,
        *,
        user: User,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        request_type: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list, int]:
        applicant_id = user.id if user.role == "BUSINESS" else None
        officer_id = user.id if user.role in ("LMO", "GATC") else None
        district = user.district if (user.role in ("LMO", "GATC") and user.district) else None
        return self.repo.search(
            page=page, page_size=page_size, search=search, status=status,
            request_type=request_type, applicant_id=applicant_id, officer_id=officer_id,
            district=district, sort_by=sort_by, sort_order=sort_order,
        )

    def get(self, req: VerificationRequest, user: User) -> dict:
        self._assert_owner(req, user, allow_officer=True)
        return req

    def get_by_public_id(self, public_id: str) -> VerificationRequest:
        req = self.repo.get_by_public_id(public_id)
        if req is None:
            raise NotFoundError("Verification request", public_id)
        return req

    # ------------------------------------------------------------------
    def _resolve_instrument(self, data: VerificationRequestCreate, user: User) -> Instrument:
        instrument = None
        if data.instrument_public_id:
            instrument = self.instruments.get_by_public_id(data.instrument_public_id)
        elif data.instrument_id:
            instrument = self.instruments.get(data.instrument_id)
        if instrument is None:
            raise NotFoundError("Instrument", data.instrument_public_id or str(data.instrument_id))
        if instrument.owner_id != user.id and user.role != "ADMIN":
            raise ValidationError("You can only file requests for instruments you own.")
        return instrument

    def _assert_owner(self, req: VerificationRequest, user: User, allow_officer: bool = False) -> None:
        if user.role == "ADMIN":
            return
        if user.role in ("LMO", "GATC") and allow_officer:
            return
        if req.applicant_id != user.id:
            raise ValidationError("You do not have access to this request.")

    def _assert_officer(self, req: VerificationRequest, officer: User) -> None:
        if officer.role == "ADMIN":
            return
        if officer.role not in ("LMO", "GATC"):
            raise ValidationError("Only an LMO/GATC or admin can schedule inspections.")
        if req.assigned_officer_id and req.assigned_officer_id != officer.id:
            raise ValidationError("This request is assigned to another officer.")

    # ------------------------------------------------------------------
    def latest_certificate(self, req: VerificationRequest) -> Optional[Certificate]:
        return req.certificates[0] if req.certificates else None