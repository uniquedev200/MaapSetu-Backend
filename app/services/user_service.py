"""User account, business-profile and settings service."""

from typing import Optional

from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.core.enums import UserRole, UserStatus
from app.core.exceptions import ConflictError, ValidationError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.audit_service import audit
from app.utils.id_generator import user_id


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)

    # -- Admin user management ------------------------------------------
    def create_user(self, *, actor: User, data) -> User:
        email = data.email.lower().strip()
        if self.repo.get_by_email(email):
            raise ConflictError("An account with this email already exists.")
        user = self.repo.create(
            public_id=user_id(),
            name=data.name,
            email=email,
            phone=data.phone,
            password_hash=hash_password(data.password),
            role=data.role.value,
            status=UserStatus.ACTIVE.value,
            district=data.district,
            business_name=data.business_name,
            registration_no=data.registration_no,
            tax_id=data.tax_id,
            address=data.address,
            settings={"notifications": {"email": True, "sms": False}, "two_factor_auth": False, "theme": "light"},
        )
        audit(self.db, user=actor, action="CREATE", entity_type="user", entity_id=user.public_id,
              details=f"Admin created {data.role.value} account for {email}")
        return user

    def update_user(self, *, actor: User, user: User, data) -> User:
        updates = data.model_dump(exclude_unset=True)
        password = updates.pop("password", None)
        if "email" in updates:
            email = updates["email"].lower().strip()
            existing = self.repo.get_by_email(email)
            if existing and existing.id != user.id:
                raise ConflictError("An account with this email already exists.")
            updates["email"] = email
        for key, value in updates.items():
            if value is not None:
                setattr(user, key, value.value if hasattr(value, "value") else value)
        if password:
            user.password_hash = hash_password(password)
        self.repo.save(user)
        audit(self.db, user=actor, action="UPDATE", entity_type="user", entity_id=user.public_id,
              details="Admin updated user account")
        return user

    def search(self, *, page: int, page_size: int, search: Optional[str] = None,
               role: Optional[str] = None, status: Optional[str] = None,
               district: Optional[str] = None) -> tuple[list, int]:
        return self.repo.search(page=page, page_size=page_size, search=search,
                                role=role, status=status, district=district)

    def get_by_public_id(self, public_id: str) -> User:
        from app.core.exceptions import NotFoundError

        user = self.repo.get_by_public_id(public_id)
        if user is None:
            raise NotFoundError("User", public_id)
        return user

    # -- Business profile ------------------------------------------------
    def business_profile(self, user: User) -> dict:
        from app.schemas.serializers import business_profile

        return business_profile(user)

    def update_business_profile(self, *, user: User, data) -> User:
        updates = data.model_dump(exclude_unset=True, exclude_none=True)
        for key, value in updates.items():
            setattr(user, key, value)
        self.repo.save(user)
        audit(self.db, user=user, action="UPDATE", entity_type="user", entity_id=user.public_id,
              details="Business profile updated")
        return user

    # -- Settings --------------------------------------------------------
    def get_settings(self, user: User) -> dict:
        defaults = {"notifications": {"email": True, "sms": False}, "two_factor_auth": False, "theme": "light"}
        settings = dict(user.settings or {})
        for k, v in defaults.items():
            settings.setdefault(k, v)
        return settings

    def update_settings(self, *, user: User, data) -> dict:
        current = dict(user.settings or {})
        patch = data.model_dump(exclude_unset=True, exclude_none=True)
        if "notifications" in patch and isinstance(patch["notifications"], dict):
            merged = dict(current.get("notifications") or {})
            merged.update(patch.pop("notifications"))
            patch["notifications"] = merged
        current.update(patch)
        user.settings = current
        self.repo.save(user)
        return self.get_settings(user)