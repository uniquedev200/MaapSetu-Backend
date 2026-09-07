"""Health score repository."""

from typing import List, Optional

from sqlalchemy import select

from app.models.health_score import HealthScore
from app.repositories.base import BaseRepository


class HealthScoreRepository(BaseRepository[HealthScore]):
    model = HealthScore

    def latest_for(self, instrument_id: int) -> Optional[HealthScore]:
        stmt = (
            select(HealthScore)
            .where(HealthScore.instrument_id == instrument_id)
            .order_by(HealthScore.computed_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def history_for(self, instrument_id: int, limit: int = 20) -> List[HealthScore]:
        stmt = (
            select(HealthScore)
            .where(HealthScore.instrument_id == instrument_id)
            .order_by(HealthScore.computed_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())