"""Audit log endpoints (admin)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import AppServices, get_services
from app.auth.deps import require_admin
from app.core.response import paginated
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.schemas.serializers import audit_log_item

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get("", summary="List audit logs (admin), raw array + pagination headers")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=200),
    action: Optional[str] = Query(None),
    user: User = Depends(require_admin),
    services: AppServices = Depends(get_services),
):
    items, total = AuditRepository(services.db).list_logs(
        page=page, page_size=page_size, search=search, action=action,
    )
    return paginated([audit_log_item(x) for x in items], total, page, page_size)