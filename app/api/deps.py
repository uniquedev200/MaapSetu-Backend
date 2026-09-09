"""Dependency-injection container for application services."""

from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.assignment_service import AssignmentService
from app.services.audit_service import audit
from app.services.auth_service import AuthService
from app.services.certificate_service import CertificateService
from app.services.dashboard_service import DashboardService
from app.services.health_score_service import HealthScoreService
from app.services.inspection_service import InspectionService
from app.services.instrument_service import InstrumentService
from app.services.notification_service import NotificationService
from app.services.passport_service import PassportService
from app.services.upload_service import UploadService
from app.services.user_service import UserService
from app.services.verification_service import VerificationService


class AppServices:
    """Lazily initialised container exposing every application service
    bound to the request's database session."""

    def __init__(self, db: Session):
        self.db = db
        self._services: dict = {}

    def __getattr__(self, name: str):
        if name in self._services:
            return self._services[name]
        factory = {
            "auth": lambda: AuthService(self.db),
            "users": lambda: UserService(self.db),
            "instruments": lambda: InstrumentService(self.db),
            "notifications": lambda: NotificationService(self.db),
            "verifications": lambda: VerificationService(self.db),
            "inspections": lambda: InspectionService(self.db),
            "certificates": lambda: CertificateService(self.db),
            "health": lambda: HealthScoreService(self.db),
            "passport": lambda: PassportService(self.db),
            "assignment": lambda: AssignmentService(self.db),
            "dashboard": lambda: DashboardService(self.db),
            "uploads": lambda: UploadService(self.db),
        }.get(name)
        if factory is None:
            raise AttributeError(name)
        service = factory()
        self._services[name] = service
        return service


def get_services(db: Session = Depends(get_db)) -> AppServices:
    return AppServices(db)


def client_ip(request: Request) -> Optional[str]:
    """Best-effort client IP from the request."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def base_url(request: Request) -> str:
    """Public base URL of this deployment (used for QR verification URLs)."""
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    scheme = forwarded_proto or request.url.scheme
    host = forwarded_host or request.headers.get("host") or request.url.netloc
    return f"{scheme}://{host}"


async def log_audit(
    request: Request,
    services: AppServices,
    actor,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    details: Optional[str] = None,
) -> None:
    audit(
        services.db,
        user=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=client_ip(request),
    )