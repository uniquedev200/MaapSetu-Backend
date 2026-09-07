"""User management schemas (admin)."""

from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.enums import UserRole


class UserAdminCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    phone: Optional[str] = None
    role: UserRole = UserRole.BUSINESS
    district: Optional[str] = None
    business_name: Optional[str] = None
    registration_no: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None


class UserAdminUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    district: Optional[str] = None
    status: Optional[str] = None
    business_name: Optional[str] = None
    registration_no: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    district: Optional[str] = None
    business_name: Optional[str] = None
    address: Optional[str] = None


class SettingsUpdate(BaseModel):
    """User preference updates (``/settings``)."""

    notifications: Optional[Dict] = None
    two_factor_auth: Optional[bool] = None
    theme: Optional[str] = Field(None, max_length=20)


class UserAdminOut(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    role: str
    status: str
    district: Optional[str] = None
    business_name: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)