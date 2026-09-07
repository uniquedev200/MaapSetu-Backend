"""Authentication & account service."""

from typing import Dict, Tuple

from sqlalchemy.orm import Session

from app.auth.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.enums import UserRole, UserStatus
from app.core.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.core.config import get_settings
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.serializers import user_session
from app.services.audit_service import audit
from app.utils.id_generator import user_id


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.settings = get_settings()

    # -- Public -----------------------------------------------------------
    def signup(self, *, name: str, email: str, password: str, phone=None, district=None, business_name=None) -> Dict:
        email = email.lower().strip()
        if self.users.get_by_email(email):
            raise ConflictError("An account with this email already exists.")

        user = User(
            public_id=user_id(),
            name=name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=UserRole.BUSINESS.value,
            status=UserStatus.ACTIVE.value,
            district=district,
            business_name=business_name,
            settings={"notifications": {"email": True, "sms": False}, "two_factor_auth": False, "theme": "light"},
        )
        self.users.add(user)
        audit(self.db, user=user, action="CREATE", entity_type="user", entity_id=user.public_id,
              details=f"New {user.role} account registered")
        return self._session_payload(user)

    def login(self, *, email: str, password: str) -> Dict:
        email = email.lower().strip()
        user = self.users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Incorrect email or password.")
        if user.status == UserStatus.DISABLED.value:
            raise UnauthorizedError("This account has been disabled. Contact the administrator.")

        audit(self.db, user=user, action="LOGIN", entity_type="user", entity_id=user.public_id, details="User logged in")
        return self._session_payload(user)

    def refresh(self, *, refresh_token: str) -> Dict:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except TokenError as exc:
            raise UnauthorizedError(str(exc)) from exc
        user = self.users.get_by_public_id(payload.get("sub"))
        if user is None or user.status == UserStatus.DISABLED.value:
            raise UnauthorizedError("Invalid refresh token subject.")
        return self._session_payload(user)

    def change_password(self, *, user: User, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, user.password_hash):
            raise ValidationError("Current password is incorrect.")
        user.password_hash = hash_password(new_password)
        self.users.save(user)
        audit(self.db, user=user, action="UPDATE", entity_type="user", entity_id=user.public_id,
              details="Password changed")

    # -- Internals --------------------------------------------------------
    def _session_payload(self, user: User) -> Dict:
        access = create_access_token(user.public_id, user.role)
        refresh = create_refresh_token(user.public_id, user.role)
        return {
            "token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "user": user_session(user),
        }