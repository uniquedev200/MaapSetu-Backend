"""Verification request data-access repository."""

from typing import Any, List, Optional, Tuple

from sqlalchemy import func, or_, select

from app.core.enums import RequestStatus
from app.models.instrument import Instrument
from app.models.verification_request import VerificationRequest
from app.repositories.base import BaseRepository


class VerificationRepository(BaseRepository[VerificationRequest]):
    model = VerificationRequest

    def get_by_public_id(self, public_id: str) -> Optional[VerificationRequest]:
        return self.get_by(public_id=public_id)

    def first_active_for_instrument(self, instrument_id: int) -> Optional[VerificationRequest]:
        active = [s.value for s in RequestStatus if s.is_active]
        stmt = (
            select(VerificationRequest)
            .where(VerificationRequest.instrument_id == instrument_id)
            .where(VerificationRequest.status.in_(active))
            .order_by(VerificationRequest.created_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def search(
        self,
        *,
        page: int,
        page_size: int,
        search: Optional[str] = None,
        status: Optional[str] = None,
        request_type: Optional[str] = None,
        applicant_id: Optional[int] = None,
        officer_id: Optional[int] = None,
        instrument_id: Optional[int] = None,
        district: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[VerificationRequest], int]:
        stmt = select(VerificationRequest)
        count_stmt = select(func.count()).select_from(VerificationRequest)

        conditions: List[Any] = []
        if applicant_id is not None:
            conditions.append(VerificationRequest.applicant_id == applicant_id)

        # Officers should always see requests explicitly assigned to them.
        # The district filter is a courtesy narrowing, but it must never hide
        # an explicit assignment (e.g. when the instrument's district is unset),
        # so assignments OR with the district condition rather than AND.
        if officer_id is not None:
            officer_cond = VerificationRequest.assigned_officer_id == officer_id
            if district:
                conditions.append(or_(officer_cond, VerificationRequest.instrument.has(district=district)))
            else:
                conditions.append(officer_cond)
        elif district:
            conditions.append(VerificationRequest.instrument.has(district=district))

        if instrument_id is not None:
            conditions.append(VerificationRequest.instrument_id == instrument_id)
        if status:
            conditions.append(VerificationRequest.status == status)
        if request_type:
            conditions.append(VerificationRequest.request_type == request_type)
        if search:
            like = f"%{search}%"
            conditions.append(
                or_(
                    VerificationRequest.public_id.ilike(like),
                    VerificationRequest.instrument.has(
                        or_(
                            Instrument.public_id.ilike(like),
                            Instrument.name.ilike(like),
                            Instrument.serial_number.ilike(like),
                        )
                    ),
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        sort_col = getattr(VerificationRequest, sort_by, VerificationRequest.created_at)
        order = sort_col.desc() if sort_order == "desc" else sort_col.asc()
        stmt = stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)

        return list(self.db.execute(stmt).scalars().all()), int(self.db.execute(count_stmt).scalar_one())