"""User admin + session endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AppServices, get_services
from app.auth.deps import get_current_user, require_admin
from app.core.enums import UserRole
from app.core.response import paginated
from app.models.user import User
from app.schemas.serializers import public_user
from app.schemas.user import UserAdminCreate, UserAdminUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=dict, summary="Current user session")
def get_me(user: User = Depends(get_current_user)) -> dict:
    return public_user(user)


@router.get("", summary="List users (admin), raw array + pagination headers")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=100),
    role: Optional[UserRole] = Query(None),
    status: Optional[str] = Query(None),
    district: Optional[str] = Query(None, max_length=200),
    user: User = Depends(require_admin),
    services: AppServices = Depends(get_services),
):
    items, total = services.users.search(
        page=page, page_size=page_size, search=search,
        role=role.value if role else None, status=status, district=district,
    )
    return paginated([public_user(u) for u in items], total, page, page_size)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, summary="Create a user (admin)")
def create_user(
    payload: UserAdminCreate,
    user: User = Depends(require_admin),
    services: AppServices = Depends(get_services),
) -> dict:
    return public_user(services.users.create_user(actor=user, data=payload))


@router.get("/{user_id}", response_model=dict, summary="User detail (admin)")
def get_user(
    user_id: str,
    user: User = Depends(require_admin),
    services: AppServices = Depends(get_services),
) -> dict:
    return public_user(services.users.get_by_public_id(user_id))


@router.patch("/{user_id}", response_model=dict, summary="Update a user (admin)")
def update_user(
    user_id: str,
    payload: UserAdminUpdate,
    user: User = Depends(require_admin),
    services: AppServices = Depends(get_services),
) -> dict:
    target = services.users.get_by_public_id(user_id)
    return public_user(services.users.update_user(actor=user, user=target, data=payload))