"""API v1 router — aggregates all endpoint modules."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    assistant,
    audit_logs,
    auth,
    business,
    certificates,
    dashboard,
    inspections,
    instruments,
    public,
    settings,
    uploads,
    users,
    verification,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(assistant.router)
api_router.include_router(users.router)
api_router.include_router(instruments.router)
api_router.include_router(verification.router)
api_router.include_router(inspections.router)
api_router.include_router(certificates.router)
api_router.include_router(dashboard.router)
api_router.include_router(public.router)
api_router.include_router(business.router)
api_router.include_router(settings.router)
api_router.include_router(audit_logs.router)
api_router.include_router(uploads.router)