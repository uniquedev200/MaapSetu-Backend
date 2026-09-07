"""Audit log repository."""

from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    def list_logs(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[AuditLog], int]:
        stmt = select(AuditLog)
        count_stmt = select(func.count()).select_from(AuditLog)

        conditions = []
        if action:
            conditions.append(AuditLog.action == action)
        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if search:
            like = f"%{search}%"
            conditions.append(
                or_(
                    AuditLog.user_name.ilike(like),
                    AuditLog.details.ilike(like),
                    AuditLog.action.ilike(like),
                    AuditLog.entity_id.ilike(like),
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        sort_col = getattr(AuditLog, sort_by, AuditLog.created_at)
        order = sort_col.desc() if sort_order == "desc" else sort_col.asc()
        stmt = stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)

        return list(self.db.execute(stmt).scalars().all()), int(self.db.execute(count_stmt).scalar_one())