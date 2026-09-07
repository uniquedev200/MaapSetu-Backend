"""Storage service abstraction (local filesystem or Supabase Storage).

StorageService is selected in startup based on ``STORAGE_BACKEND`` so the app
runs fully locally out-of-the-box and switches to Supabase simply via config.
"""

import errno
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings


class StorageBackend(ABC):
    """Minimal storage contract (upload / public url / delete)."""

    @abstractmethod
    def upload(self, *, folder: str, filename: str, content: bytes) -> str:
        """Persist bytes and return the storage object path."""

    @abstractmethod
    def public_url(self, path: str) -> str:
        """Return a publicly fetchable URL for a stored object."""

    @abstractmethod
    def delete(self, path: str) -> None:
        """Remove a stored object (best effort)."""

    def make_filename(self, original: str) -> str:
        suffix = Path(original).suffix or ".bin"
        return f"{uuid.uuid4().hex}{suffix}"


class LocalStorageBackend(StorageBackend):
    """Stores files on disk under ``UPLOAD_DIR`` and serves them via the
    ``/api/v1/public/file/...`` route."""

    def __init__(self) -> None:
        self.root = Path(get_settings().UPLOAD_DIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, path: str) -> Path:
        candidate = (self.root / path).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise ValueError("Invalid storage path")
        return candidate

    def upload(self, *, folder: str, filename: str, content: bytes) -> str:
        obj_path = f"{folder}/{filename}"
        target = self._safe_path(obj_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return f"{folder}/{filename}"

    def public_url(self, path: str) -> str:
        return f"/api/v1/public/file/{path}"

    def delete(self, path: str) -> None:
        try:
            self._safe_path(path).unlink(missing_ok=True)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise

    def read(self, path: str) -> bytes:
        return self._safe_path(path).read_bytes()


class SupabaseStorageBackend(StorageBackend):
    """Persists objects to a Supabase Storage bucket using the service-role key."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY are required when STORAGE_BACKEND=supabase"
            )
        from supabase import create_client

        self._client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        self._bucket = settings.SUPABASE_STORAGE_BUCKET

    def upload(self, *, folder: str, filename: str, content: bytes) -> str:
        obj_path = f"{folder}/{filename}"
        self._client.storage.from_(self._bucket).upload(
            path=obj_path,
            file=content,
            file_options={"content-type": "application/octet-stream", "upsert": "true"},
        )
        return obj_path

    def public_url(self, path: str) -> str:
        return self._client.storage.from_(self._bucket).get_public_url(path)

    def delete(self, path: str) -> None:
        try:
            self._client.storage.from_(self._bucket).remove([path])
        except Exception:  # pragma: no cover
            pass


class StorageService:
    """Session-free facade over the active storage backend."""

    def __init__(self) -> None:
        settings = get_settings()
        if settings.STORAGE_BACKEND == "supabase":
            self._backend: StorageBackend = SupabaseStorageBackend()
        else:
            self._backend = LocalStorageBackend()

    def upload(self, *, folder: str, filename: str, content: bytes) -> str:
        safe = Path(filename).name  # strip any path components
        return self._backend.upload(folder=folder, filename=safe, content=content)

    def make_filename(self, original: str) -> str:
        return self._backend.make_filename(original)

    def public_url(self, path: str) -> str:
        return self._backend.public_url(path)

    def delete(self, path: str) -> None:
        self._backend.delete(path)

    def read(self, path: str) -> bytes:
        if isinstance(self._backend, LocalStorageBackend):
            return self._backend.read(path)
        raise NotImplementedError("Remote read is not supported; use public_url instead.")


storage_service = StorageService()