"""Inspection output schemas."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class InspectionOut(BaseModel):
    id: str
    date: Optional[str] = None
    inspector: Optional[str] = None
    location: Optional[str] = None
    status: str
    result: Optional[str] = None
    request_id: Optional[str] = None
    instrument_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InspectionDetail(InspectionOut):
    inspection_date: Optional[date] = None
    scheduled_date: Optional[date] = None
    load_test: Optional[float] = None
    eccentricity: Optional[float] = None
    is_within_tolerance: Optional[bool] = None
    observations: Optional[str] = None
    remarks: Optional[str] = None
    photos: List[str] = []
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)