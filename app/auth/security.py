"""Password hashing (passlib PBKDF2) and JWT utilities (python-jose)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# PBKDF2-SHA256 avoids native/circular dependencies and is well supported on
# every platform (including Windows) with no compilation required.
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    default="pbkdf2_sha256",
    pbkdf2_sha256__default_rounds=settings.PASSWORD_ROUNDS,
    deprecated="auto",
)


class TokenError(Exception):
    """Raised when a JWT is invalid, expired or malformed."""


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, role: str, expires_minutes: Optional[int] = None) -> str:
    """Create a signed JWT access token with ``sub`` and ``role`` claims."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    claims = {"sub": subject, "role": role, "type": "access"}
    claims.update({"exp": expire})
    return jwt.encode(claims, settings.secret_key, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    claims = {"sub": subject, "role": role, "type": "refresh"}
    claims.update({"exp": expire})
    return jwt.encode(claims, settings.secret_key, algorithm=settings.ALGORITHM)


def decode_token(token: str, expected_type: Optional[str] = "access") -> Dict[str, Any]:
    """Decode and validate a token. Raises ``TokenError`` on any failure."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise TokenError("Token is invalid or expired") from exc
    except Exception as exc:  # pragma: no cover
        raise TokenError("Token could not be decoded") from exc

    if expected_type and payload.get("type") != expected_type:
        raise TokenError(f"Expected a {expected_type} token")
    subject = payload.get("sub")
    if not subject:
        raise TokenError("Token is missing the subject claim")
    return payload


def parse_token_payload(token: str) -> Dict[str, Any]:
    return decode_token(token)


def token_expiry_delta(token: str) -> timedelta:
    """Remaining validity of an access token (used for refresh responses)."""
    payload = decode_token(token)
    exp_ts = payload.get("exp")
    if not exp_ts:
        return timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    remaining = datetime.fromtimestamp(exp_ts, tz=timezone.utc) - datetime.now(timezone.utc)
    return remaining if remaining > timedelta(0) else timedelta(minutes=0)