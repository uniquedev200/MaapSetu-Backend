"""Instrument endpoints (register, list, retrieve, update, photo upload)."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.api.deps import AppServices, get_services
from app.auth.deps import get_current_user, require_business
from app.core.response import paginated
from app.models.user import User
from app.schemas.instrument import ComplaintCreate, InstrumentCreate, InstrumentUpdate
from app.schemas.serializers import instrument_detail, instrument_list_item
from app.services.upload_service import ALLOWED_IMAGE_TYPES

router = APIRouter(prefix="/instruments", tags=["Instruments"])


@router.get("", summary="List instruments (role-scoped), raw array + pagination headers")
def list_instruments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=100),
    instrument_type: Optional[str] = Query(None, max_length=120),
    status: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
):
    items, total = services.instruments.list(
        user=user, page=page, page_size=page_size, search=search,
        instrument_type=instrument_type, status=status,
    )
    return paginated([instrument_list_item(i) for i in items], total, page, page_size)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, summary="Register an instrument")
def create_instrument(
    payload: InstrumentCreate,
    user: User = Depends(require_business),
    services: AppServices = Depends(get_services),
) -> dict:
    return instrument_detail(services.instruments.create(user=user, data=payload))


@router.patch("/{instrument_id}", response_model=dict, summary="Update an instrument")
def update_instrument(
    instrument_id: str,
    payload: InstrumentUpdate,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    instrument = services.instruments.get_by_public_id(instrument_id, current_user=user)
    updated = services.instruments.update(instrument=instrument, user=user, data=payload)
    return instrument_detail(updated)


@router.get("/{instrument_id}", response_model=dict, summary="Instrument detail")
def get_instrument(
    instrument_id: str,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    return instrument_detail(services.instruments.get_by_public_id(instrument_id, current_user=user))


@router.post("/{instrument_id}/complaint", response_model=dict, summary="Log a complaint against an instrument")
def log_complaint(
    instrument_id: str,
    payload: ComplaintCreate,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    instrument = services.instruments.get_by_public_id(instrument_id, current_user=user)
    updated = services.instruments.register_complaint(
        instrument=instrument, user=user,
        description=payload.description, severity=payload.severity,
    )
    return instrument_detail(updated)


@router.post("/{instrument_id}/photo", response_model=dict, summary="Upload an instrument photo")
async def upload_instrument_photo(
    instrument_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    services.instruments.get_by_public_id(instrument_id, current_user=user)
    path, _url = await services.uploads.save(
        file=file, folder=f"instruments/{instrument_id}",
        allowed=ALLOWED_IMAGE_TYPES, user=user,
    )
    return instrument_detail(services.instruments.attach_photo(public_id=instrument_id, path=path))