"""FastAPI dependencies: current user resolution and RBAC guards."""

from typing import Callable, List, Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import TokenError, decode_token
from app.core.enums import UserRole, UserStatus
from app.core.exceptions import AuthorizationError, UnauthorizedError
from app.db.session import get_db
from app.models.user import User
from app.middleware.request_context import set_current_user
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve and return the authenticated user from the Bearer token."""
    if credentials is None:
        raise UnauthorizedError("Not authenticated. Provide a valid access token.")

    try:
        payload = decode_token(credentials.credentials)
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc

    public_id = payload.get("sub")
    if not public_id:
        raise UnauthorizedError("Token subject missing")

    repo = UserRepository(db)
    user = repo.get_by_public_id(public_id)
    if user is None:
        raise UnauthorizedError("User account no longer exists")
    if user.status == UserStatus.DISABLED.value:
        raise UnauthorizedError("User account is disabled")

    set_current_user(user.public_id)
    return user


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """RBAC guard factory — restricts an endpoint to one or more roles."""

    allowed = [r.value for r in roles]

    def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise AuthorizationError(
                f"This action is restricted to roles: {', '.join(allowed)}."
            )
        return user

    return _guard


require_business = require_roles(UserRole.BUSINESS)
require_lmo = require_roles(UserRole.LMO)
require_gatc = require_roles(UserRole.GATC)
require_officer = require_roles(UserRole.LMO, UserRole.GATC)
require_admin = require_roles(UserRole.ADMIN)


def optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Resolve the current user if a valid token is supplied (never raises)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except TokenError:
        return None
    user = UserRepository(db).get_by_public_id(payload.get("sub", ""))
    return user