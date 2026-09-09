"""In-app notifications — available to every authenticated role."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import AppServices, get_services
from app.auth.deps import get_current_user
from app.core.response import ok
from app.models.user import User
from app.schemas.serializers import notification_item

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=dict, summary="Current user notification feed")
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: Optional[bool] = Query(None, description="Filter to unread items only"),
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    items, total = services.notifications.list_for(
        user=user, page=page, page_size=page_size, unread_only=unread_only
    )
    return ok(
        "Notifications",
        {
            "items": [notification_item(n) for n in items],
            "total": total,
            "unread": services.notifications.unread_count(user),
        },
    )


@router.get("/unread-count", response_model=dict, summary="Unread notification count")
def unread_count(
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    return ok("Unread count", {"count": services.notifications.unread_count(user)})


@router.post("/read-all", response_model=dict, summary="Mark all notifications as read")
def read_all(
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    marked = services.notifications.mark_all_read(user)
    return ok("All notifications marked as read", {"marked": marked})


@router.post("/{notification_id}/read", response_model=dict, summary="Mark one notification as read")
def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    notification = services.notifications.mark_read(notification_id, user)
    return ok("Notification marked as read", notification_item(notification))