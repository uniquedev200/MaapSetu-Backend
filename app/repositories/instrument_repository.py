"""Instrument data-access repository."""

from typing import Any, List, Optional, Tuple

from sqlalchemy import func, or_, select

from app.models.inspection import Inspection
from app.models.verification_request import VerificationRequest

from app.models.instrument import Instrument
from app.repositories.base import BaseRepository


class InstrumentRepository(BaseRepository[Instrument]):
    model = Instrument

    def get_by_public_id(self, public_id: str) -> Optional[Instrument]:
        return self.get_by(public_id=public_id)

    def get_by_serial(self, serial_number: str) -> Optional[Instrument]:
        return self.get_by(serial_number=serial_number)

    def list_for_owner(self, owner_id: int) -> List[Instrument]:
        return self.query(Instrument.owner_id == owner_id)

    def search(
        self,
        *,
        page: int,
        page_size: int,
        search: Optional[str] = None,
        status: Optional[str] = None,
        instrument_type: Optional[str] = None,
        district: Optional[str] = None,
        owner_id: Optional[int] = None,
        officer_id: Optional[int] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Instrument], int]:
        stmt = select(Instrument)
        count_stmt = select(func.count()).select_from(Instrument)

        conditions: List[Any] = []
        if owner_id is not None:
            conditions.append(Instrument.owner_id == owner_id)
        if officer_id is not None:
            # Officers only see instruments linked to their assigned requests
            # or inspections they have performed.
            conditions.append(
                or_(
                    Instrument.requests.any(VerificationRequest.assigned_officer_id == officer_id),
                    Instrument.requests.any(
                        VerificationRequest.inspections.any(Inspection.inspector_id == officer_id)
                    ),
                )
            )
        if status:
            conditions.append(Instrument.status == status)
        if instrument_type:
            conditions.append(Instrument.instrument_type == instrument_type)
        if district:
            conditions.append(Instrument.district == district)
        if search:
            like = f"%{search}%"
            conditions.append(
                or_(
                    Instrument.serial_number.ilike(like),
                    Instrument.name.ilike(like),
                    Instrument.instrument_type.ilike(like),
                    Instrument.manufacturer.ilike(like),
                    Instrument.model_number.ilike(like),
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        sort_col = getattr(Instrument, sort_by, Instrument.created_at)
        order = sort_col.desc() if sort_order == "desc" else sort_col.asc()
        stmt = stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)

        return list(self.db.execute(stmt).scalars().all()), int(self.db.execute(count_stmt).scalar_one())