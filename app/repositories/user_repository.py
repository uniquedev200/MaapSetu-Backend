"""Repositories for the core domain aggregate roots."""

from typing import Any, List, Optional, Sequence, Tuple

from sqlalchemy import func, or_, select

from app.core.enums import UserRole, UserStatus
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_email(self, email: str) -> Optional[User]:
        return self.get_by(email=email)

    def get_by_public_id(self, public_id: str) -> Optional[User]:
        return self.get_by(public_id=public_id)

    def list_officers(
        self,
        *,
        district: Optional[str] = None,
        roles: Optional[Sequence[str]] = None,
        active_only: bool = True,
    ) -> List[User]:
        """Return officers, optionally scoped to a district."""
        roles = list(roles or [UserRole.LMO.value, UserRole.GATC.value])
        stmt = select(User).where(User.role.in_(roles))
        if active_only:
            stmt = stmt.where(User.status == UserStatus.ACTIVE.value)
        if district:
            stmt = stmt.where(User.district == district)
        return list(self.db.execute(stmt).scalars().all())

    def active_workload(self, officer_id: int) -> int:
        """Count genuinely open requests currently assigned to an officer.

        Completed/certificate-issued work no longer consumes the officer's
        capacity, so the smart-assigner can balance new work correctly.
        """
        from app.models.verification_request import VerificationRequest

        stmt = (
            select(func.count())
            .select_from(VerificationRequest)
            .where(VerificationRequest.assigned_officer_id == officer_id)
            .where(VerificationRequest.status.in_(
                ["SUBMITTED", "APPROVED", "ASSIGNED_LMO", "SCHEDULED", "IN_PROGRESS"]
            ))
        )
        return int(self.db.execute(stmt).scalar_one())

    def search(
        self,
        *,
        page: int,
        page_size: int,
        search: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        district: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[User], int]:
        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)

        conditions: List[Any] = []
        if role:
            conditions.append(User.role == role)
        if status:
            conditions.append(User.status == status)
        if district:
            conditions.append(User.district == district)
        if search:
            like = f"%{search}%"
            conditions.append(
                or_(
                    User.name.ilike(like),
                    User.email.ilike(like),
                    User.phone.ilike(like),
                    User.business_name.ilike(like),
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        sort_col = getattr(User, sort_by, User.created_at)
        order = sort_col.desc() if sort_order == "desc" else sort_col.asc()
        stmt = stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)

        return list(self.db.execute(stmt).scalars().all()), int(self.db.execute(count_stmt).scalar_one())


class OfficerRepository(UserRepository):
    """Alias repository for roles with officer semantics."""

    pass