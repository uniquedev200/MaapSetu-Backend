"""Certificate data-access repository."""

from datetime import date
from typing import Any, List, Optional, Tuple

from sqlalchemy import func, or_, select

from app.core.enums import CertificateStatus
from app.models.certificate import Certificate
from app.models.instrument import Instrument
from app.repositories.base import BaseRepository


class CertificateRepository(BaseRepository[Certificate]):
    model = Certificate

    def get_by_public_id(self, public_id: str) -> Optional[Certificate]:
        return self.get_by(public_id=public_id)

    def get_by_certificate_number(self, certificate_number: str) -> Optional[Certificate]:
        return self.get_by(certificate_number=certificate_number)

    def last_for_instrument(self, instrument_id: int) -> Optional[Certificate]:
        stmt = (
            select(Certificate)
            .where(Certificate.instrument_id == instrument_id)
            .where(Certificate.status == CertificateStatus.ACTIVE.value)
            .order_by(Certificate.issued_date.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def expiring_in(self, within_days: int, *, owner_id: Optional[int] = None) -> List[Certificate]:
        """Certificates that expire between today and today+``within_days``."""
        from datetime import timedelta

        today = date.today()
        horizon = today + timedelta(days=within_days)
        stmt = select(Certificate).where(
            Certificate.status == CertificateStatus.ACTIVE.value,
            Certificate.expiry_date >= today,
            Certificate.expiry_date <= horizon,
        )
        if owner_id is not None:
            stmt = stmt.where(Certificate.owner_id == owner_id)
        return list(self.db.execute(stmt).scalars().all())

    def search(
        self,
        *,
        page: int,
        page_size: int,
        search: Optional[str] = None,
        status: Optional[str] = None,
        owner_id: Optional[int] = None,
        district: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Certificate], int]:
        stmt = select(Certificate)
        count_stmt = select(func.count()).select_from(Certificate)

        conditions: List[Any] = []
        if owner_id is not None:
            conditions.append(Certificate.owner_id == owner_id)
        if status:
            conditions.append(Certificate.status == status)
        if district:
            conditions.append(Certificate.instrument.has(district=district))
        if search:
            like = f"%{search}%"
            conditions.append(
                or_(
                    Certificate.certificate_number.ilike(like),
                    Certificate.instrument.has(
                        or_(
                            Instrument.name.ilike(like),
                            Instrument.serial_number.ilike(like),
                        )
                    ),
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        sort_col = getattr(Certificate, sort_by, Certificate.created_at)
        order = sort_col.desc() if sort_order == "desc" else sort_col.asc()
        stmt = stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)

        return list(self.db.execute(stmt).scalars().all()), int(self.db.execute(count_stmt).scalar_one())