"""Verification request & inspection schemas."""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import RequestType


class VerificationRequestCreate(BaseModel):
    instrument_id: Optional[int] = Field(None, description="Numeric instrument PK")
    instrument_public_id: Optional[str] = Field(None, description="Public instrument id (INST-...)")
    request_type: RequestType = RequestType.NEW_VERIFICATION
    preferred_date: Optional[date] = None
    remarks: Optional[str] = Field(None, max_length=2000)
    submit_now: bool = True


class VerificationRequestUpdate(BaseModel):
    instrument_id: Optional[int] = None
    request_type: Optional[RequestType] = None
    preferred_date: Optional[date] = None
    remarks: Optional[str] = None


class ScheduleInspection(BaseModel):
    scheduled_date: date
    scheduled_location: Optional[str] = Field(None, max_length=255)


class AssignRequest(BaseModel):
    officer_id: Optional[int] = None
    entity_type: Optional[str] = Field(None, description="LMO or GATC")
    strategy: str = Field("auto", description="auto | lowest_workload | district | manual")


class InspectionFindings(BaseModel):
    """Accepts both snake_case (API-first) and the camelCase field names the
    React FieldInspection page posts (``loadTest``, ``eccentricity``,
    ``isWithinTolerance``, ``notes``)."""

    load_test: Optional[float] = Field(None, alias="loadTest")
    applied_load: Optional[float] = Field(None, alias="appliedLoad",
                                          description="Nominal test load applied (same unit as instrument)")
    eccentricity: Optional[float] = Field(None, alias="eccentricity")
    is_within_tolerance: Optional[bool] = Field(None, alias="isWithinTolerance")
    notes: Optional[str] = Field(None, max_length=2000)
    remarks: Optional[str] = Field(None, max_length=2000)
    observations: Optional[str] = Field(None, max_length=4000)
    photos: List[str] = Field(default_factory=list)
    result: Optional[str] = Field(None, description="PASS or FAIL (auto-derived if omitted)")

    model_config = ConfigDict(populate_by_name=True)


class RequestListOut(BaseModel):
    id: str
    type: str
    status: str
    created_at: Optional[str] = None
    instrument_name: Optional[str] = None
    request_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RequestBusinessInfo(BaseModel):
    business_name: str
    registration_number: Optional[str] = None
    location: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None


class RequestInstrumentItem(BaseModel):
    name: str
    serial: str
    icon: str = "scale"
    type: str = "Routine"
    typeClass: Optional[str] = None
    class_: Optional[str] = Field(None, alias="class")


class RequestDetail(BaseModel):
    id: str
    type: str
    status: str
    request_type: str
    business_name: str
    registration_number: Optional[str] = None
    location: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    instruments: List[RequestInstrumentItem]
    created_at: Optional[str] = None
    remarks: Optional[str] = None
    inspection: Optional[dict] = None
    certificate: Optional[dict] = None