"""Serializers — convert ORM objects into the exact JSON shapes the React
frontend consumes (see BACKEND_INTEGRATION_GUIDE.md).

Keeping these explicit makes the frontend contract auditable in one place.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.enums import RequestType
from app.models.certificate import Certificate
from app.models.inspection import Inspection
from app.models.instrument import Instrument
from app.models.user import User
from app.models.verification_request import VerificationRequest


def iso_date(value: Optional[date | datetime]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value.isoformat()


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------
def instrument_list_item(inst: Instrument) -> Dict[str, Any]:
    """Shape documented in BACKEND_INTEGRATION_GUIDE.md §3."""
    return {
        "id": inst.public_id,
        "serial_number": inst.serial_number,
        "instrument_type": inst.instrument_type,
        "name": inst.name,
        "model_number": inst.model_number,
        "manufacturer": inst.manufacturer,
        "capacity_max": inst.capacity_max,
        "capacity_min": inst.capacity_min,
        "unit_of_measurement": inst.unit_of_measurement,
        "accuracy_class": inst.accuracy_class,
        "verification_interval_e": inst.verification_interval_e,
        "verification_frequency_months": inst.verification_frequency_months,
        "status": inst.status,
        "district": inst.district,
        "installation_location": inst.installation_location,
        "photo_url": inst.photo_url,
        "health_score": inst.health_score,
    }


def instrument_detail(inst: Instrument) -> Dict[str, Any]:
    """Full instrument payload (create/update/detail endpoints)."""
    return {
        **instrument_list_item(inst),
        "installed_at": iso_date(inst.installed_at),
        "created_at": iso_date(inst.created_at),
        "updated_at": iso_date(inst.updated_at),
        "owner_id": inst.owner_id,
    }


# ---------------------------------------------------------------------------
# Verification requests
# ---------------------------------------------------------------------------
def request_list_item(req: VerificationRequest) -> Dict[str, Any]:
    """Shape documented in BACKEND_INTEGRATION_GUIDE.md §3."""
    return {
        "id": req.public_id,
        "type": req.type_display,
        "status": req.status,
        "created_at": iso_date(req.created_at),
        "request_type": req.request_type,
    }


def _instrument_icon(instrument_type: str) -> str:
    lowered = (instrument_type or "").lower()
    if "flow" in lowered:
        return "water"
    if "therm" in lowered or "temperature" in lowered:
        return "device_thermostat"
    if "length" in lowered or "tape" in lowered:
        return "straighten"
    return "scale"


def request_detail(req: VerificationRequest, extra: Optional[dict] = None,
                   current_user: Optional["User"] = None) -> Dict[str, Any]:
    """Full application detail consumed by ApplicationDetails.tsx /
    FieldInspection.tsx (business info + instruments array)."""
    applicant: User = req.applicant
    instruments: List[Instrument] = [req.instrument]

    payload: Dict[str, Any] = {
        "id": req.public_id,
        "type": req.type_display,
        "status": req.status,
        "request_type": req.request_type,
        "business_name": applicant.business_name or applicant.name,
        "registration_number": applicant.registration_no or "",
        "location": req.instrument.installation_location or applicant.address or "",
        "contact_person": applicant.name,
        "contact_phone": applicant.phone or "",
        "created_at": iso_date(req.created_at),
        "remarks": req.remarks,
        "preferred_date": iso_date(req.preferred_date),
        "scheduled_date": iso_date(req.scheduled_date),
        "scheduled_location": req.scheduled_location,
        "assigned_officer": req.assigned_officer.name if req.assigned_officer else None,
        "assigned_entity_type": req.assigned_entity_type,
        "assigned_to_me": bool(current_user and req.assigned_officer_id == current_user.id),
        "rejection_reason": req.rejection_reason or "",
        "district": req.instrument.district,
        "instruments": [
            {
                "id": inst.public_id,
                "name": inst.name,
                "serial": inst.serial_number,
                "icon": _instrument_icon(inst.instrument_type),
                "type": req.type_display,
                "class": inst.accuracy_class or "Class III",
                "accuracy_class": inst.accuracy_class or "Class III",
                "instrument_type": inst.instrument_type,
                "model_number": inst.model_number,
                "capacity_max": inst.capacity_max,
                "unit_of_measurement": inst.unit_of_measurement,
            }
            for inst in instruments
        ],
    }
    if extra:
        payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Inspections
# ---------------------------------------------------------------------------
def inspection_list_item(insp: Inspection) -> Dict[str, Any]:
    """Shape documented in BACKEND_INTEGRATION_GUIDE.md §3. The frontend tracks
    PENDING / COMPLETED / FAILED, so scheduled inspections surface as PENDING."""
    display_status = {
        "SCHEDULED": "PENDING",
        "IN_PROGRESS": "IN_PROGRESS",
        "COMPLETED": "COMPLETED",
        "FAILED": "FAILED",
    }.get(insp.status, insp.status)

    return {
        "id": insp.public_id,
        "date": iso_date(insp.inspection_date or insp.scheduled_date),
        "inspector": insp.inspector.name if insp.inspector else None,
        "status": display_status,
        "location": insp.location_display,
        "result": insp.result,
        "request_id": insp.request.public_id if insp.request else None,
        "instrument_name": insp.instrument.name if insp.instrument else None,
    }


def inspection_detail(insp: Inspection) -> Dict[str, Any]:
    """Full inspection payload (detail endpoint)."""
    return {
        **inspection_list_item(insp),
        "scheduled_date": iso_date(insp.scheduled_date),
        "inspection_date": iso_date(insp.inspection_date),
        "load_test": insp.load_test,
        "applied_load": insp.applied_load,
        "eccentricity": insp.eccentricity,
        "is_within_tolerance": insp.is_within_tolerance,
        "deviation_g": insp.deviation_g,
        "mpe_g": insp.mpe_g,
        "metrology_standard": insp.metrology_standard,
        "observations": insp.observations,
        "remarks": insp.remarks,
        "photos": list(insp.photos or []),
        "instrument_id": insp.instrument.public_id if insp.instrument else None,
    }


# ---------------------------------------------------------------------------
# Certificates
# ---------------------------------------------------------------------------
def certificate_list_item(cert: Certificate) -> Dict[str, Any]:
    """Shape documented in BACKEND_INTEGRATION_GUIDE.md §3."""
    return {
        "id": cert.public_id,
        "certificate_number": cert.certificate_number,
        "instrument": cert.instrument.name if cert.instrument else "",
        "instrument_name": cert.instrument.name if cert.instrument else "",
        "serial_number": cert.instrument.serial_number if cert.instrument else None,
        "business_name": cert.owner.business_name or cert.owner.name if cert.owner else None,
        "issued_date": iso_date(cert.issued_date),
        "valid_until": iso_date(cert.expiry_date),
        "issue_date": iso_date(cert.issued_date),
        "expiry": iso_date(cert.expiry_date),
        "status": cert.status,
        "inspector_name": cert.inspector.name if cert.inspector else None,
        "pdf_url": cert.pdf_url,
        "qr_code_url": cert.qr_code_url,
        "certificate_hash": cert.certificate_hash,
        "block_index": cert.block_index,
        "block_hash": cert.block_hash,
        "verification_url": cert.verification_url,
        "request_id": cert.request.public_id if cert.request else None,
        "is_tampered": cert.is_tampered,
    }


# ---------------------------------------------------------------------------
# Users / auth / business / audit
# ---------------------------------------------------------------------------
def user_session(user: User) -> Dict[str, Any]:
    return {
        "id": user.public_id,
        "name": user.display_name,
        "email": user.email,
        "role": user.role,
        "phone": user.phone,
        "district": user.district,
    }


def public_user(user: User) -> Dict[str, Any]:
    """Admin-facing user record (full profile attributes)."""
    return {
        "id": user.public_id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "status": user.status,
        "district": user.district,
        "business_name": user.business_name,
        "registration_no": user.registration_no,
        "tax_id": user.tax_id,
        "address": user.address,
        "created_at": iso_date(user.created_at),
    }


def business_profile(user: User) -> Dict[str, Any]:
    return {
        "business_name": user.business_name or user.name,
        "status": "ACTIVE" if user.status == "ACTIVE" else user.status,
        "registration_no": user.registration_no or "",
        "tax_id": user.tax_id or "",
        "address": user.address or "",
        "owner": user.name,
        "phone": user.phone or "",
        "email": user.email,
    }


def audit_log_item(log: Any) -> Dict[str, Any]:
    return {
        "id": log.id,
        "timestamp": iso_date(log.created_at),
        "user": log.user_name or "System",
        "action": log.action,
        "details": log.details or "",
    }