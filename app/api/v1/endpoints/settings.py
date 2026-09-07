"""User settings endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import AppServices, get_services
from app.auth.deps import get_current_user
from app.models.user import User
from app.schemas.user import SettingsUpdate

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=dict, summary="Current user settings")
def get_settings(
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    return services.users.get_settings(user)


@router.patch("", response_model=dict, summary="Update user settings")
def update_settings(
    payload: SettingsUpdate,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    return services.users.update_settings(user=user, data=payload)