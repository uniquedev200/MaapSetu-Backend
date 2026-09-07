"""Authentication and session schemas.

The shapes below match the React frontend contract documented in
``SIH-36-Frontend/BACKEND_INTEGRATION_GUIDE.md`` (login/signup return
``{token, user: {id, name, email, role}}``).
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    phone: Optional[str] = Field(None, max_length=20)
    district: Optional[str] = Field(None, max_length=120)
    business_name: Optional[str] = Field(None, max_length=160)


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class UserSession(BaseModel):
    """User payload returned in login/signup/me responses."""

    id: str
    name: str
    email: str
    role: str
    phone: Optional[str] = None
    district: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserSession