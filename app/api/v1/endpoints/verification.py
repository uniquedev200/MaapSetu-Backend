"""Verification request lifecycle endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AppServices, get_services
from app.auth.deps import get_current_user, require_admin, require_business, require_officer
from app.core.exceptions import ValidationError
from app.core.response import ok, paginated
from app.models.user import User
from app.schemas.serializers import certificate_list_item, request_detail, request_list_item
from app.schemas.verification import (
    AssignRequest,
    InspectionFindings,
    ScheduleInspection,
    VerificationRequestCreate,
    VerificationRequestUpdate,
)

router = APIRouter(tags=["Verification"])


def _resolve(req_id: str, services: AppServices):
    return services.verifications.get_by_public_id(req_id)


def _detail_with_cert(req, services: AppServices, user=None) -> dict:
    extra = {}
    cert = services.verifications.latest_certificate(req)
    if cert is not None:
        extra["certificate"] = certificate_list_item(cert)
    return request_detail(req, extra, user)


@router.get("/verification", summary="List verification requests (role-scoped)")
def list_verifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=100),
    status: Optional[str] = Query(None),
    request_type: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
):
    items, total = services.verifications.list(
        user=user, page=page, page_size=page_size, search=search,
        status=status, request_type=request_type,
    )
    return paginated([request_list_item(r) for r in items], total, page, page_size)


@router.get("/verification/{request_id}/assign-options", response_model=dict,
            summary="Available officers in the district + workloads (admin)")
def assign_options(
    request_id: str,
    user: User = Depends(require_admin),
    services: AppServices = Depends(get_services),
) -> dict:
    req = _resolve(request_id, services)
    return ok(
        "Assignable officers",
        services.assignment.available_officers(req.instrument),
    )


@router.post("/verification", response_model=dict, status_code=status.HTTP_201_CREATED,
             summary="Create a verification request")
def create_verification(
    payload: VerificationRequestCreate,
    user: User = Depends(require_business),
    services: AppServices = Depends(get_services),
) -> dict:
    return _detail_with_cert(services.verifications.create(user=user, data=payload), services, user)


@router.get("/verification/{request_id}", response_model=dict, summary="Verification request detail")
def get_verification(
    request_id: str,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    req = _resolve(request_id, services)
    services.verifications.get(req, user)
    return _detail_with_cert(req, services, user)


@router.patch("/verification/{request_id}", response_model=dict, summary="Update a draft request")
def update_verification(
    request_id: str,
    payload: VerificationRequestUpdate,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    req = _resolve(request_id, services)
    req = services.verifications.update(req, user, payload)
    return _detail_with_cert(req, services, user)


@router.post("/verification/{request_id}/submit", response_model=dict,
             summary="Submit a draft request")
def submit_verification(
    request_id: str,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    req = _resolve(request_id, services)
    return _detail_with_cert(services.verifications.submit(req, user), services, user)


@router.post("/verification/{request_id}/approve", response_model=dict,
             summary="Approve and auto-assign (admin)")
def approve_verification(
    request_id: str,
    payload: Optional[AssignRequest] = None,
    user: User = Depends(require_admin),
    services: AppServices = Depends(get_services),
) -> dict:
    req = _resolve(request_id, services)
    payload = payload or AssignRequest()
    req = services.verifications.approve_and_assign(
        req, user,
        officer_id=payload.officer_id,
        entity_type=payload.entity_type,
        strategy=payload.strategy,
    )
    return _detail_with_cert(req, services, user)


@router.post("/verification/{request_id}/assign", response_model=dict,
             summary="Assign an approved request (admin)")
def assign_verification(
    request_id: str,
    payload: AssignRequest,
    user: User = Depends(require_admin),
    services: AppServices = Depends(get_services),
) -> dict:
    req = _resolve(request_id, services)
    if payload.officer_id:
        req = services.verifications.approve_and_assign(
            req, user, officer_id=payload.officer_id, strategy="manual"
        )
    else:
        req = services.verifications.approve_and_assign(
            req, user, entity_type=payload.entity_type, strategy=payload.strategy
        )
    return _detail_with_cert(req, services, user)


@router.post("/verification/{request_id}/schedule", response_model=dict,
             summary="Schedule an inspection (officer)")
def schedule_verification(
    request_id: str,
    payload: ScheduleInspection,
    user: User = Depends(require_officer),
    services: AppServices = Depends(get_services),
) -> dict:
    req = _resolve(request_id, services)
    req = services.verifications.schedule(
        req, user, scheduled_date=payload.scheduled_date,
        scheduled_location=payload.scheduled_location,
    )
    return _detail_with_cert(req, services, user)


@router.post("/verification/{request_id}/inspect", response_model=dict,
             summary="Submit inspection findings (officer)")
def inspect_verification(
    request_id: str,
    payload: InspectionFindings,
    user: User = Depends(require_officer),
    services: AppServices = Depends(get_services),
) -> dict:
    req = _resolve(request_id, services)
    return services.verifications.inspect(req, user, payload)


@router.post("/verification/{request_id}/cancel", response_model=dict,
             summary="Cancel a request")
def cancel_verification(
    request_id: str,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    req = _resolve(request_id, services)
    return _detail_with_cert(services.verifications.cancel(req, user), services, user)
