"""Domain enumerations shared across models, schemas and services."""

from enum import Enum


class StrEnum(str, Enum):
    """String enum with ``Enum.value`` semantics for serialization and DB storage."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]


class UserRole(StrEnum):
    """Role-Based Access Control roles.

    ``LMO``  — Legal Metrology Officer.
    ``GATC`` — Government Approved Test Centre (officer equivalent for RBAC).
    """

    BUSINESS = "BUSINESS"
    LMO = "LMO"
    GATC = "GATC"
    ADMIN = "ADMIN"

    @property
    def is_officer(self) -> bool:
        return self in (UserRole.LMO, UserRole.GATC)


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class InstrumentStatus(StrEnum):
    """Lifecycle status of a registered instrument (matches frontend contract)."""

    REGISTERED = "REGISTERED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    UNDER_VERIFICATION = "UNDER_VERIFICATION"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class RequestStatus(StrEnum):
    """Status flow for a verification request.

    Flow: DRAFT → SUBMITTED → APPROVED → SCHEDULED → ASSIGNED_LMO → IN_PROGRESS
    → COMPLETED → CERTIFICATE_ISSUED.  Terminals: REJECTED, CANCELLED.
    """

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    ASSIGNED_LMO = "ASSIGNED_LMO"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CERTIFICATE_ISSUED = "CERTIFICATE_ISSUED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in (
            RequestStatus.CERTIFICATE_ISSUED,
            RequestStatus.REJECTED,
            RequestStatus.CANCELLED,
        )

    @property
    def is_active(self) -> bool:
        return self not in (RequestStatus.DRAFT, RequestStatus.CANCELLED, RequestStatus.REJECTED)


class RequestType(StrEnum):
    NEW_VERIFICATION = "NEW_VERIFICATION"
    RE_VERIFICATION = "RE_VERIFICATION"
    RENEWAL = "RENEWAL"

    @property
    def display(self) -> str:
        return {
            RequestType.NEW_VERIFICATION: "New Verification",
            RequestType.RE_VERIFICATION: "Re-verification",
            RequestType.RENEWAL: "Renewal",
        }[self]


class InspectionStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class InspectionResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class CertificateStatus(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"


class HealthCategory(StrEnum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    CRITICAL = "CRITICAL"


class PassportEventType(StrEnum):
    REGISTERED = "REGISTERED"
    VERIFICATION_REQUESTED = "VERIFICATION_REQUESTED"
    REQUEST_APPROVED = "REQUEST_APPROVED"
    ASSIGNED = "ASSIGNED"
    INSPECTION_SCHEDULED = "INSPECTION_SCHEDULED"
    INSPECTION_PASSED = "INSPECTION_PASSED"
    INSPECTION_FAILED = "INSPECTION_FAILED"
    CERTIFICATE_ISSUED = "CERTIFICATE_ISSUED"
    COMPLAINT = "COMPLAINT"
    HEALTH_UPDATED = "HEALTH_UPDATED"
    OVERDUE = "OVERDUE"
    MANUAL = "MANUAL"


class AuditAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    SUBMIT = "SUBMIT"
    APPROVE = "APPROVE"
    ASSIGN = "ASSIGN"
    SCHEDULE = "SCHEDULE"
    INSPECT = "INSPECT"
    CERTIFICATE = "CERTIFICATE"
    VERIFY = "VERIFY"
    UPLOAD = "UPLOAD"
    OTHER = "OTHER"