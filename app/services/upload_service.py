"""File upload handling (local filesystem or Supabase storage bucket)."""

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.enums import AuditAction
from app.models.user import User
from app.services.audit_service import audit
from app.services.storage_service import storage_service

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_DOC_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/csv",
    "text/plain",
    "image/jpeg",
    "image/png",
    "image/webp",
}


class UploadService:
    def __init__(self, db):
        self.db = db
        self.settings = get_settings()

    def _validate(self, file: UploadFile, allowed: set) -> None:
        if file.content_type not in allowed:
            raise ValueError(
                f"Unsupported file type '{file.content_type}'. "
                f"Allowed: {', '.join(sorted(allowed))}"
            )

    async def save(
        self,
        file: UploadFile,
        folder: str,
        allowed: set | None = None,
        user: User | None = None,
    ) -> tuple[str, str]:
        """Persist an uploaded file and return ``(storage_path, public_url)``."""
        allowed = allowed if allowed is not None else ALLOWED_DOC_TYPES
        self._validate(file, allowed)

        safe_name = storage_service.make_filename(file.filename or "upload.bin")
        folder = folder.strip("/")
        raw = await file.read()

        if self.settings.STORAGE_BACKEND == "supabase":
            path = storage_service.upload(folder=folder, filename=safe_name, content=raw)
        else:
            path = storage_service.upload(folder=folder, filename=safe_name, content=raw)

        if user is not None:
            audit(
                self.db, user=user, action=AuditAction.UPLOAD.value,
                entity_type="file", entity_id=path,
                details=f"Uploaded file '{safe_name}' to {folder}/",
            )
        return path, storage_service.public_url(path)