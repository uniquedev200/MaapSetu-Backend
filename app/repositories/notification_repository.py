"""Notification data-access repository."""

from typing import List, Optional, Tuple

from sqlalchemy import func, select, update

from app.db.base import utcnow
from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    def for_user(
        self,
        *,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        unread_only: Optional[bool] = None,
    ) -> Tuple[List[Notification], int]:
        """Most-recent-first notification page for a user."""
        stmt = select(Notification).where(Notification.user_id == user_id)
        count_stmt = select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
            count_stmt = count_stmt.where(Notification.is_read.is_(False))
        total = int(self.db.execute(count_stmt).scalar_one())
        stmt = (
            stmt.order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.execute(stmt).scalars().all()), total

    def unread_count(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        return int(self.db.execute(stmt).scalar_one())

    def get_for_user(self, notification_id: int, user_id: int) -> Optional[Notification]:
        return self.get_by(id=notification_id, user_id=user_id)

    def mark_read(self, notification: Notification, *, user_id: int) -> Notification:
        if notification.user_id != user_id:
            return notification
        notification.mark_read()
        return self.save(notification)

    def mark_all_read(self, user_id: int) -> int:
        result = self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True, read_at=utcnow())
        )
        self.db.commit()
        return result.rowcount or 0