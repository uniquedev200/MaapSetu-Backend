"""Inspection endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import AppServices, get_services
from app.auth.deps import get_current_user
from app.core.response import paginated
from app.models.user import User
from app.schemas.serializers import inspection_detail, inspection_list_item

router = APIRouter(prefix="/inspections", tags=["Inspections"])


@router.get("", summary="List inspections (role-scoped), raw array + pagination headers")
def list_inspections(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=100),
    status: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
):
    items, total = services.inspections.list(
        user=user, page=page, page_size=page_size, search=search, status=status,
    )
    return paginated([inspection_list_item(i) for i in items], total, page, page_size)


@router.get("/{inspection_id}", response_model=dict, summary="Inspection detail")
def get_inspection(
    inspection_id: str,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    return inspection_detail(services.inspections.get(inspection_id))