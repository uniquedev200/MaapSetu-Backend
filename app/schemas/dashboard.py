"""Dashboard, business-profile, settings and audit-log schemas."""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class DashboardMetrics(BaseModel):
    """Exactly the keys the frontend Dashboard reads."""

    registered_instruments: int
    active_applications: int
    valid_certificates: int
    expiring_soon: int

    model_config = ConfigDict(from_attributes=True)


class BusinessDashboard(BaseModel):
    my_instruments: int
    active_certificates: int
    expiring_certificates: int
    pending_applications: int
    health_distribution: dict


class OfficerDashboard(BaseModel):
    assigned_requests: int
    pending_inspections: int
    completed_inspections: int
    passed: int
    failed: int


class AdminDashboard(BaseModel):
    total_instruments: int
    total_certificates: int
    pending_requests: int
    total_lmos: int
    total_gatcs: int
    total_businesses: int
    verification_statistics: dict
    recent_verifications: Optional[list] = None


class BusinessProfileOut(BaseModel):
    business_name: str
    status: str
    registration_no: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    owner: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BusinessProfileUpdate(BaseModel):
    business_name: Optional[str] = None
    registration_no: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class SettingsOut(BaseModel):
    notifications: dict
    two_factor_auth: bool
    theme: str

    model_config = ConfigDict(from_attributes=True)


class SettingsUpdate(BaseModel):
    notifications: Optional[dict] = None
    two_factor_auth: Optional[bool] = None
    theme: Optional[str] = None


class AuditLogOut(BaseModel):
    id: int
    timestamp: str
    user: str
    action: str
    details: str

    model_config = ConfigDict(from_attributes=True)