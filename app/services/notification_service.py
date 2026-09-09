"""In-app notification service plus a best-effort emit helper.

The ``notify`` helper is the single entry point for workflow events and is
deliberately non-fatal — a notification must never break a business flow.
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.models.notification import Notification
from app.models.user import User
from app.repositories.notification_repository import NotificationRepository


def notify(
    db: Session,
    *,
    user_id: int,
    title: str,
    message: str,
    type: str = "SYSTEM",
    link: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    actor_id: Optional[int] = None,
) -> Optional[Notification]:
    """Persist a single notification. Never raises."""
    try:
        return NotificationRepository(db).create(
            user_id=user_id,
            actor_id=actor_id,
            title=title,
            message=message,
            type=type,
            link=link,
            payload=payload or {},
            is_read=False,
        )
    except Exception:  # pragma: no cover - notifications must be non-fatal
        return None


def notify_admins(
    db: Session,
    *,
    title: str,
    message: str,
    type: str = "SYSTEM",
    link: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    actor_id: Optional[int] = None,
) -> None:
    """Fan out a notification to every ADMIN account. Never raises."""
    try:
        admin_ids = db.execute(select(User.id).where(User.role == UserRole.ADMIN.value)).scalars().all()
    except Exception:  # pragma: no cover
        return
    for admin_id in admin_ids:
        notify(db, user_id=admin_id, title=title, message=message, type=type,
               link=link, payload=payload, actor_id=actor_id)


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = NotificationRepository(db)

    def list_for(
        self,
        *,
        user: User,
        page: int = 1,
        page_size: int = 20,
        unread_only: Optional[bool] = None,
    ) -> Tuple[List[Notification], int]:
        return self.repo.for_user(user_id=user.id, page=page, page_size=page_size, unread_only=unread_only)

    def unread_count(self, user: User) -> int:
        return self.repo.unread_count(user.id)

    def mark_read(self, notification_id: int, user: User) -> Notification:
        from app.core.exceptions import NotFoundError

        notification = self.repo.get_for_user(notification_id, user.id)
        if notification is None:
            raise NotFoundError("Notification", str(notification_id))
        return self.repo.mark_read(notification, user_id=user.id)

    def mark_all_read(self, user: User) -> int:
        return self.repo.mark_all_read(user.id)