"""Role-aware dashboard endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import AppServices, get_services
from app.auth.deps import get_current_user, require_admin, require_business, require_officer
from app.core.response import ok
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/metrics", response_model=dict, summary="Card metrics for the React dashboard")
def dashboard_metrics(
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    return services.dashboard.metrics(user)


@router.get("/business", response_model=dict, summary="Business dashboard (role-scoped)")
def business_dashboard(
    user: User = Depends(require_business),
    services: AppServices = Depends(get_services),
) -> dict:
    return services.dashboard.business_dashboard(user)


@router.get("/officer", response_model=dict, summary="Officer dashboard (LMO/GATC)")
def officer_dashboard(
    user: User = Depends(require_officer),
    services: AppServices = Depends(get_services),
) -> dict:
    return services.dashboard.officer_dashboard(user)


@router.get("/admin", response_model=dict, summary="Admin analytics dashboard (envelope)")
def admin_dashboard(
    user: User = Depends(require_admin),
    services: AppServices = Depends(get_services),
) -> dict:
    return ok("Admin dashboard analytics", services.dashboard.admin_dashboard())