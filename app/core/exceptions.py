"""Domain-specific exceptions and global HTTP error mapping."""

from typing import Any, Optional

from fastapi import HTTPException, status


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, *, code: str = "APP_ERROR", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: Optional[str] = None, code: str = "NOT_FOUND"):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(message, code=code, status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str, code: str = "CONFLICT"):
        super().__init__(message, code=code, status_code=409)


class ValidationError(AppError):
    def __init__(self, message: str, *, code: str = "VALIDATION_ERROR"):
        super().__init__(message, code=code, status_code=422)


class AuthorizationError(AppError):
    def __init__(
        self,
        message: str = "You do not have permission to perform this action.",
        *,
        code: str = "FORBIDDEN",
    ):
        super().__init__(message, code=code, status_code=403)


class UnauthorizedError(AppError):
    def __init__(
        self,
        message: str = "Authentication credentials are required.",
        *,
        code: str = "UNAUTHORIZED",
    ):
        super().__init__(message, code=code, status_code=401)


def to_http_exception(exc: AppError) -> HTTPException:
    """Convert an ``AppError`` into a FastAPI ``HTTPException`` with a frontend-friendly body."""
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.message,
        headers={"X-Error-Code": exc.code},
    )


def detail(message: str, data: Any = None) -> dict[str, Any]:
    """Build the standard error payload used across the API."""
    return {"detail": message}