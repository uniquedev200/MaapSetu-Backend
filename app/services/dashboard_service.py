"""Role-aware dashboard metrics."""

from datetime import date
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import CertificateStatus, RequestStatus, UserRole
from app.models.certificate import Certificate
from app.models.inspection import Inspection
from app.models.instrument import Instrument
from app.models.user import User
from app.models.verification_request import VerificationRequest
from app.repositories.certificate_repository import CertificateRepository
from app.repositories.verification_repository import VerificationRepository


class DashboardService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    # -- Frontend dashboard (/dashboard/metrics) -------------------------
    def metrics(self, user: User) -> Dict[str, Any]:
        """Exactly the four keys the React Dashboard reads."""
        return {
            "registered_instruments": self._count_instruments(user),
            "active_applications": self._count_active_requests(user),
            "valid_certificates": self._count_active_certificates(user),
            "expiring_soon": len(self._expiring_certificates(user)),
        }

    # -- Role-specific dashboards ----------------------------------------
    def business_dashboard(self, user: User) -> Dict[str, Any]:
        from app.repositories.instrument_repository import InstrumentRepository

        instruments = InstrumentRepository(self.db).list_for_owner(user.id)
        certificates = CertificateRepository(self.db).search(
            page=1, page_size=1, owner_id=user.id)[0]
        certs = CertificateRepository(self.db).query(Certificate.owner_id == user.id)
        active_certs = [c for c in certs if c.status == CertificateStatus.ACTIVE.value]
        expiring = self._expiring_certificates(user)

        pending = [
            r for r in VerificationRepository(self.db).query(VerificationRequest.applicant_id == user.id)
            if r.status in (RequestStatus.SUBMITTED.value, RequestStatus.APPROVED.value,
                            RequestStatus.ASSIGNED_LMO.value, RequestStatus.SCHEDULED.value,
                            RequestStatus.IN_PROGRESS.value, RequestStatus.COMPLETED.value)
        ]

        distribution = {"EXCELLENT": 0, "GOOD": 0, "NEEDS_ATTENTION": 0, "CRITICAL": 0}
        for inst in instruments:
            category = (
                "EXCELLENT" if inst.health_score >= 90
                else "GOOD" if inst.health_score >= 70
                else "NEEDS_ATTENTION" if inst.health_score >= 50
                else "CRITICAL"
            )
            distribution[category] += 1

        return {
            "my_instruments": len(instruments),
            "active_certificates": len(active_certs),
            "expiring_certificates": len(expiring),
            "pending_applications": len(pending),
            "health_distribution": distribution,
        }

    def officer_dashboard(self, user: User) -> Dict[str, Any]:
        from app.repositories.inspection_repository import InspectionRepository

        requests = VerificationRepository(self.db).query(
            VerificationRequest.assigned_officer_id == user.id
        )
        active_statuses = [
            RequestStatus.SUBMITTED.value, RequestStatus.APPROVED.value,
            RequestStatus.ASSIGNED_LMO.value, RequestStatus.SCHEDULED.value,
            RequestStatus.IN_PROGRESS.value, RequestStatus.COMPLETED.value,
        ]
        assigned = [r for r in requests if r.status in active_statuses]
        pending = [r for r in requests if r.status in (RequestStatus.ASSIGNED_LMO.value, RequestStatus.SCHEDULED.value, RequestStatus.IN_PROGRESS.value)]
        completed = [r for r in requests if r.status == RequestStatus.CERTIFICATE_ISSUED.value]

        inspections = InspectionRepository(self.db).query(Inspection.inspector_id == user.id)
        passed = sum(1 for i in inspections if i.result == "PASS")
        failed = sum(1 for i in inspections if i.result == "FAIL")

        return {
            "assigned_requests": len(assigned),
            "pending_inspections": len(pending),
            "completed_inspections": len(completed),
            "passed": passed,
            "failed": failed,
        }

    def admin_dashboard(self) -> Dict[str, Any]:
        from datetime import datetime, timedelta, timezone

        total_instruments = self._count_instruments(None)
        total_certificates = self._count_active_certificates(None)
        pending = self._count_active_requests(None)
        lmos = self._count_users(UserRole.LMO.value)
        gatcs = self._count_users(UserRole.GATC.value)
        businesses = self._count_users(UserRole.BUSINESS.value)

        # Verification statistics over the last 6 months.
        months = 6
        since = datetime.now(timezone.utc) - timedelta(days=months * 30)
        issued_count = int(
            self.db.execute(
                select(func.count()).select_from(Certificate)
                .where(Certificate.created_at >= since)
            ).scalar_one()
        )
        failed_count = int(
            self.db.execute(
                select(func.count()).select_from(VerificationRequest)
                .where(VerificationRequest.status == RequestStatus.REJECTED.value)
                .where(VerificationRequest.created_at >= since)
            ).scalar_one()
        )
        instr_by_status_rows = self.db.execute(
            select(Instrument.status, func.count())
            .group_by(Instrument.status)
        ).all()

        return {
            "total_instruments": total_instruments,
            "total_certificates": total_certificates,
            "pending_requests": pending,
            "total_lmos": lmos,
            "total_gatcs": gatcs,
            "total_businesses": businesses,
            "verification_statistics": {
                "certificates_issued_last_6_months": issued_count,
                "rejected_requests_last_6_months": failed_count,
                "instruments_by_status": {status: count for status, count in instr_by_status_rows},
            },
        }

    # -- Helpers ---------------------------------------------------------
    def _count_users(self, role: str) -> int:
        from app.models.user import User as UserModel

        stmt = select(func.count()).select_from(UserModel).where(UserModel.role == role)
        return int(self.db.execute(stmt).scalar_one())

    def _count_instruments(self, user: Optional[User]) -> int:
        stmt = select(func.count()).select_from(Instrument)
        if user is not None and user.role == UserRole.BUSINESS.value:
            stmt = stmt.where(Instrument.owner_id == user.id)
        elif user is not None and user.role in (UserRole.LMO.value, UserRole.GATC.value) and user.district:
            stmt = stmt.where(Instrument.district == user.district)
        return int(self.db.execute(stmt).scalar_one())

    def _count_active_requests(self, user: Optional[User]) -> int:
        active = [s.value for s in RequestStatus if s.is_active]
        stmt = select(func.count()).select_from(VerificationRequest).where(VerificationRequest.status.in_(active))
        if user is not None and user.role == UserRole.BUSINESS.value:
            stmt = stmt.where(VerificationRequest.applicant_id == user.id)
        elif user is not None and user.role in (UserRole.LMO.value, UserRole.GATC.value) and user.district:
            stmt = stmt.where(VerificationRequest.instrument.has(district=user.district))
        return int(self.db.execute(stmt).scalar_one())

    def _count_active_certificates(self, user: Optional[User]) -> int:
        stmt = select(func.count()).select_from(Certificate).where(Certificate.status == CertificateStatus.ACTIVE.value)
        if user is not None and user.role == UserRole.BUSINESS.value:
            stmt = stmt.where(Certificate.owner_id == user.id)
        return int(self.db.execute(stmt).scalar_one())

    def _expiring_certificates(self, user: Optional[User]) -> list:
        owner_id = user.id if (user is not None and user.role == UserRole.BUSINESS.value) else None
        return CertificateRepository(self.db).expiring_in(
            self.settings.CERTIFICATE_EXPIRY_WARNING_DAYS, owner_id=owner_id
        )