"""Passport events repository."""

from typing import List

from sqlalchemy import select

from app.models.passport_event import PassportEvent
from app.repositories.base import BaseRepository


class PassportRepository(BaseRepository[PassportEvent]):
    model = PassportEvent

    def for_instrument(self, instrument_id: int) -> List[PassportEvent]:
        stmt = (
            select(PassportEvent)
            .where(PassportEvent.instrument_id == instrument_id)
            .order_by(PassportEvent.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())