"""Instrument registration schemas (MVP + frontend contract)."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InstrumentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    instrument_type: str = Field(min_length=2, max_length=120)
    manufacturer: Optional[str] = Field(None, max_length=160)
    model_number: Optional[str] = Field(None, max_length=80)
    serial_number: str = Field(min_length=2, max_length=120)
    capacity_max: Optional[float] = Field(None, gt=0)
    capacity_min: Optional[float] = Field(None, ge=0)
    unit_of_measurement: str = Field("kg", max_length=20)
    accuracy_class: Optional[str] = Field("Class III", max_length=40)
    verification_interval_e: Optional[float] = Field(None, gt=0, description="Verification scale interval 'e' in grams (OIML R76)")
    installation_location: Optional[str] = Field(None, max_length=255)
    district: Optional[str] = Field(None, max_length=120)
    verification_frequency_months: int = Field(12, ge=1, le=120)
    installed_at: Optional[date] = None


class InstrumentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    instrument_type: Optional[str] = Field(None, min_length=2, max_length=120)
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    capacity_max: Optional[float] = None
    capacity_min: Optional[float] = None
    unit_of_measurement: Optional[str] = None
    accuracy_class: Optional[str] = None
    verification_interval_e: Optional[float] = None
    installation_location: Optional[str] = None
    district: Optional[str] = None
    verification_frequency_months: Optional[int] = None
    status: Optional[str] = None


class ComplaintCreate(BaseModel):
    description: str = Field(min_length=5, max_length=2000)
    severity: str = Field("MINOR", max_length=20)


class InstrumentDetail(BaseModel):
    """Full instrument payload (from_attributes ORM serialization)."""

    id: str
    serial_number: str
    instrument_type: str
    name: str
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    capacity_max: Optional[float] = None
    capacity_min: Optional[float] = None
    unit_of_measurement: str
    accuracy_class: Optional[str] = None
    verification_interval_e: Optional[float] = None
    installation_location: Optional[str] = None
    district: Optional[str] = None
    photo_url: Optional[str] = None
    status: str
    verification_frequency_months: int
    health_score: int
    owner_id: Optional[int] = None
    installed_at: Optional[date] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)