"""Context-local request metadata (request id, correlation id, timing)."""

from contextvars import ContextVar
from uuid import uuid4

current_request_id: ContextVar[str] = ContextVar("request_id", default="")
current_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)


def new_request_id() -> str:
    return uuid4().hex


def set_request_id(request_id: str) -> None:
    current_request_id.set(request_id)


def get_request_id() -> str:
    return current_request_id.get()


def set_current_user(user_id: str) -> None:
    current_user_id.set(user_id)