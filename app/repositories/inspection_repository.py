"""Inspection data-access repository."""

from typing import Any, List, Optional, Tuple

from sqlalchemy import func, or_, select

from app.models.inspection import Inspection
from app.models.instrument import Instrument
from app.repositories.base import BaseRepository


class InspectionRepository(BaseRepository[Inspection]):
    model = Inspection

    def get_by_public_id(self, public_id: str) -> Optional[Inspection]:
        return self.get_by(public_id=public_id)

    def for_request(self, request_id: int) -> Optional[Inspection]:
        stmt = (
            select(Inspection)
            .where(Inspection.request_id == request_id)
            .order_by(Inspection.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def search(
        self,
        *,
        page: int,
        page_size: int,
        search: Optional[str] = None,
        status: Optional[str] = None,
        result: Optional[str] = None,
        inspector_id: Optional[int] = None,
        district: Optional[str] = None,
        owner_id: Optional[int] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Inspection], int]:
        stmt = select(Inspection)
        count_stmt = select(func.count()).select_from(Inspection)

        conditions: List[Any] = []
        if inspector_id is not None:
            conditions.append(Inspection.inspector_id == inspector_id)
        if status:
            conditions.append(Inspection.status == status)
        if result:
            conditions.append(Inspection.result == result)
        if district:
            conditions.append(Inspection.instrument.has(district=district))
        if owner_id is not None:
            conditions.append(Inspection.instrument.has(Instrument.owner_id == owner_id))
        if search:
            like = f"%{search}%"
            conditions.append(
                or_(
                    Inspection.public_id.ilike(like),
                    Inspection.instrument.has(
                        or_(
                            Instrument.serial_number.ilike(like),
                            Instrument.name.ilike(like),
                        )
                    ),
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        sort_col = getattr(Inspection, sort_by, Inspection.created_at)
        order = sort_col.desc() if sort_order == "desc" else sort_col.asc()
        stmt = stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)

        return list(self.db.execute(stmt).scalars().all()), int(self.db.execute(count_stmt).scalar_one())