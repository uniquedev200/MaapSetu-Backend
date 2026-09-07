"""Business profile & document upload endpoints."""

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import AppServices, get_services
from app.auth.deps import require_business
from app.models.user import User
from app.schemas.user import UserProfileUpdate

router = APIRouter(prefix="/business", tags=["Business"])


@router.get("/profile", response_model=dict, summary="Business profile")
def business_profile(
    user: User = Depends(require_business),
    services: AppServices = Depends(get_services),
) -> dict:
    return services.users.business_profile(user)


@router.patch("/profile", response_model=dict, summary="Update business profile")
def update_business_profile(
    payload: UserProfileUpdate,
    user: User = Depends(require_business),
    services: AppServices = Depends(get_services),
) -> dict:
    services.users.update_business_profile(user=user, data=payload)
    return services.users.business_profile(user)


@router.post("/upload-document", response_model=dict, summary="Upload a business document")
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(require_business),
    services: AppServices = Depends(get_services),
) -> dict:
    path, url = await services.uploads.save(file=file, folder="documents", user=user)
    return {"path": path, "url": url}