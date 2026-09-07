"""Certificate endpoints (list, detail, PDF download, blockchain verify)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse, Response

from app.api.deps import AppServices, get_services
from app.auth.deps import get_current_user, require_admin
from app.core.config import get_settings
from app.core.response import ok, paginated
from app.models.verification_request import VerificationRequest
from app.models.user import User
from app.schemas.serializers import certificate_list_item
from app.services.storage_service import storage_service

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.get("", summary="List certificates (role-scoped), raw array + pagination headers")
def list_certificates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = Query(None, max_length=100),
    status: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
):
    items, total = services.certificates.list_all(
        user=user, page=page, page_size=page_size, search=search, status=status,
    )
    return paginated([certificate_list_item(c) for c in items], total, page, page_size)


@router.get("/{certificate_id}", response_model=dict, summary="Certificate detail")
def get_certificate(
    certificate_id: str,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    return certificate_list_item(services.certificates.get_or_404(certificate_id))


@router.get("/{certificate_id}/verify", response_model=dict,
            summary="Blockchain verification for a certificate")
def verify_certificate(
    certificate_id: str,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    cert = services.certificates.get_or_404(certificate_id)
    return services.certificates.verify(cert, full=True)


@router.post("/{certificate_id}/tamper", response_model=dict,
             summary="Simulate tampering for the demo (admin)")
def simulate_tamper(
    certificate_id: str,
    user: User = Depends(require_admin),
    services: AppServices = Depends(get_services),
) -> dict:
    cert = services.certificates.get_or_404(certificate_id)
    cert = services.certificates.simulate_tamper(cert)
    return ok("Tamper simulation applied — verification will now fail",
              certificate_list_item(cert))


@router.post("/{certificate_id}/restore", response_model=dict,
             summary="Restore a demo-tampered certificate (admin)")
def restore_certificate(
    certificate_id: str,
    user: User = Depends(require_admin),
    services: AppServices = Depends(get_services),
) -> dict:
    cert = services.certificates.get_or_404(certificate_id)
    cert = services.certificates.restore(cert)
    return ok("Certificate restored to its authentic state", certificate_list_item(cert))


@router.get("/{certificate_id}/pdf", summary="Download the certificate PDF")
def download_certificate_pdf(
    certificate_id: str,
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> Response:
    cert = services.certificates.get_or_404(certificate_id)
    backend = get_settings().STORAGE_BACKEND
    # pdf_url may be an absolute URL (Supabase) or a local path (format below).
    if backend == "supabase" or (cert.pdf_url or "").startswith("http"):
        return RedirectResponse(url=cert.pdf_url)

    stored = cert.pdf_url
    if stored.startswith("/api/v1/public/file/"):
        stored = stored[len("/api/v1/public/file/") :]
    if stored.startswith("/"):
        stored = stored.strip("/")

    try:
        content = storage_service.read(stored)
    except FileNotFoundError:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Certificate PDF", certificate_id)
    except NotImplementedError:
        return RedirectResponse(url=cert.pdf_url or "")

    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{cert.certificate_number}.pdf"'},
    )