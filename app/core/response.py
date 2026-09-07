"""Pagination, filtering and the standard response envelope.

The existing React frontend expects *raw* JSON shapes (arrays / objects) from the
resource endpoints it consumes. Those endpoints therefore return the raw payload
directly and expose pagination metadata via HTTP headers. New / internal endpoints
(public verification, passport, blockchain, admin analytics) use the standard
``{success, message, data}`` envelope described in the system specification.
"""

from math import ceil
from typing import Any, Dict, Generic, List, Optional, TypeVar

from fastapi import Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

T = TypeVar("T")


class PageParams(BaseModel):
    """Validated pagination + query parameters for list endpoints."""

    page: int = Query(1, ge=1, description="1-indexed page number")
    page_size: int = Query(20, ge=1, le=200, description="Number of records per page")
    search: Optional[str] = Query(None, description="Free-text search term")
    sort_by: str = Query("created_at", description="Column to sort by")
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page(BaseModel, Generic[T]):
    """Paginated result container."""

    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def from_query(cls, items: List[T], total: int, params: PageParams) -> "Page[T]":
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            pages=ceil(total / params.page_size) if params.page_size else 0,
        )


def ok(message: str = "OK", data: Any = None) -> Dict[str, Any]:
    """Standard success envelope: ``{"success": true, "message": ..., "data": ...}``."""
    return {"success": True, "message": message, "data": data}


def paginated(items: List[Any], total: int, page: int, page_size: int) -> JSONResponse:
    """Raw-array response with pagination metadata as HTTP headers.

    The React frontend reads ``response.data`` as the raw array and uses
    ``X-Total-Count`` for counts (see BACKEND_INTEGRATION_GUIDE.md).
    """
    pages = ceil(total / page_size) if page_size else 0
    return JSONResponse(
        content=items,
        headers={
            "X-Total-Count": str(total),
            "X-Page": str(page),
            "X-Page-Size": str(page_size),
            "X-Pages": str(pages),
        },
    )


def envelope_error(message: str, code: str = "ERROR", data: Any = None) -> Dict[str, Any]:
    """Standard error envelope for internal endpoints."""
    return {"success": False, "message": message, "code": code, "data": data} if data is not None else {
        "success": False,
        "message": message,
        "code": code,
    }