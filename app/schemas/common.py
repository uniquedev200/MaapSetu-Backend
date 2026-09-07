"""Common / shared schema types."""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None


class PageOut(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int


class SchemaMixin(BaseModel):
    """Base for all schemas: allows attribute initialization from ORM objects."""

    model_config = ConfigDict(from_attributes=True)