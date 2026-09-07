"""Generic upload endpoint (authenticated)."""

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import AppServices, get_services
from app.auth.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post("", response_model=dict, summary="Upload a file and return its storage path + URL")
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    services: AppServices = Depends(get_services),
) -> dict:
    path, url = await services.uploads.save(file=file, folder="uploads", user=user)
    return {"path": path, "url": url}