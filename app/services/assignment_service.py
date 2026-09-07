"""Smart auto-assignment service.

Reusable and strategy-driven so it can later support route optimization,
distance calculation and priority scheduling without changing callers.
"""

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.instrument import Instrument
from app.models.user import User
from app.models.verification_request import VerificationRequest
from app.repositories.user_repository import UserRepository


class AssignmentService:
    """Assigns verification requests to the "best" LMO or GATC.

    Rules (MVP):
      . prefer officers in the same district as the instrument;
      . among them, pick the officer with the lowest active workload.

    Extensible: add ``strategy`` implementations (route optimization, distance,
    priority scheduling) without changing the ``assign`` callers.
    """

    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def assign(
        self,
        request: VerificationRequest,
        *,
        officer_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        strategy: str = "auto",
    ) -> Tuple[User, str]:
        """Assign ``request`` to an officer and persist the assignment."""
        if officer_id is not None:
            officer = self.users.get_or_404(officer_id, "Officer")
            if not self._is_officer(officer):
                raise ValidationError("The selected user is not an LMO or GATC.")
        elif entity_type:
            officer = self._pick_officer(request.instrument, roles=[entity_type])
            if officer is None:
                raise ConflictError(f"No available {entity_type} for assignment.")
        else:
            officer = self._pick_officer(request.instrument, strategy=strategy)
            if officer is None:
                raise ConflictError(
                    "No officer available for assignment in this district. Please assign manually "
                    "or add an LMO/GATC for the district."
                )

        request.assigned_officer_id = officer.id
        request.assigned_entity_type = officer.role
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return officer, officer.role

    # -- Strategy hooks ----------------------------------------------------
    def _pick_officer(
        self,
        instrument: Instrument,
        roles: Optional[List[str]] = None,
        strategy: str = "auto",
    ) -> Optional[User]:
        district = instrument.district
        candidates = self.users.list_officers(district=district, roles=roles)

        if strategy == "district_only":
            # Nothing to weigh — first candidate (district filter already applied).
            return candidates[0] if candidates else None

        if strategy == "manual":
            # Callers must supply officer_id explicitly.
            return None

        # auto | lowest_workload : same-district officers, lowest active workload.
        if not candidates:
            # Fallback: any officer (district has none registered, or instrument
            # has no district) so auto-assignment can still make progress.
            candidates = self.users.list_officers(roles=roles)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda officer: (
                # Penalise officers outside the instrument district.
                0 if (officer.district or "").lower() == (district or "").lower() else 1,
                self.users.active_workload(officer.id),
            ),
        )

    def available_officers(
        self,
        instrument: Instrument,
        entity_type: Optional[str] = None,
    ) -> List[dict]:
        """Return candidate officers for ``instrument`` plus their current
        workload and which one the auto-strategy would pick.

        Used by the admin "Approve & Assign" panel to make assignment
        transparent: same-district officers first, sorted by workload.
        """
        district = instrument.district
        roles = [entity_type] if entity_type else None
        district_candidates = self.users.list_officers(district=district, roles=roles)
        fallback_candidates = ([] if district_candidates
                               else self.users.list_officers(roles=roles))

        inspected: List[dict] = []
        for officer in district_candidates + fallback_candidates:
            workload = self.users.active_workload(officer.id)
            in_district = (officer.district or "").lower() == (district or "").lower()
            inspected.append({
                "public_id": officer.public_id,
                "id": officer.id,
                "name": officer.display_name,
                "role": officer.role,
                "district": officer.district,
                "workload": workload,
                "in_district": in_district,
            })

        # De-dupe by officer id (a fallback officer is only listed once).
        unique: List[dict] = []
        seen: set = set()
        for entry in inspected:
            if entry["id"] in seen:
                continue
            seen.add(entry["id"])
            unique.append(entry)

        unique.sort(key=lambda e: (0 if e["in_district"] else 1, e["workload"], e["name"]))

        recommended = unique[0]["public_id"] if unique else None
        for entry in unique:
            entry["recommended"] = entry["public_id"] == recommended
        return {
            "district": district,
            "entity_type": entity_type,
            "officers": unique,
            "recommended": recommended,
        }

    @staticmethod
    def _is_officer(user: User) -> bool:
        return user.role in (UserRole.LMO.value, UserRole.GATC.value)