"""Audit trail service — structured event logging to the audit_logs table."""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User
from app.middleware.request_context import get_request_id
from app.repositories.audit_repository import AuditRepository


def audit(
    db: Session,
    *,
    user: Optional[User],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    details: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Persist a single audit event. Never raises — logging must not break flows."""
    try:
        return AuditRepository(db).create(
            user_id=user.id if user else None,
            user_name=user.display_name if user else None,
            role=user.role if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            metadata_json=metadata or {},
            ip_address=ip_address,
            request_id=get_request_id(),
        )
    except Exception:  # pragma: no cover - audit must be non-fatal
        return None