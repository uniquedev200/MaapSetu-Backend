"""One-off migration: push local ``backend/storage`` artefacts into Supabase
Storage and repoint existing certificate url columns at the public CDN URLs.

Usage (from the backend folder, with the venv python)::

    $env:SUPABASE_URL      = "https://<project-ref>.supabase.co"
    $env:SUPABASE_SERVICE_KEY = "<service_role key>"
    python migrate_storage_to_supabase.py

The bucket is created publicly if missing. Object paths match what the app
already stored in the DB (``certificates/...``, ``qrcodes/...``, ``uploads/...``).
"""

import mimetypes
import os
import sys
from pathlib import Path

from supabase import create_client

import app.models  # noqa: F401  (register all model mappers/relationships)
from app.core.config import get_settings

BASE = Path(__file__).resolve().parent
STORAGE_ROOT = BASE / "storage"

if not STORAGE_ROOT.exists():
    sys.exit("No local storage dir found; nothing to migrate.")

settings = get_settings()
SUPABASE_URL = os.environ.get("SUPABASE_URL") or settings.SUPABASE_URL
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or settings.SUPABASE_SERVICE_KEY
BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET") or settings.SUPABASE_STORAGE_BUCKET

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    sys.exit("SUPABASE_URL and SUPABASE_SERVICE_KEY are required (set as env vars).")

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# 1) ensure a public bucket
bucket_names = [b.name for b in client.storage.list_buckets()]
if BUCKET not in bucket_names:
    client.storage.create_bucket(BUCKET, options={"public": True})
    print(f"[bucket] created public bucket '{BUCKET}'")
else:
    print(f"[bucket] '{BUCKET}' already exists")


def content_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


# 2) upload every local file, preserving the DB-relative object path
uploaded = 0
for file in sorted(STORAGE_ROOT.rglob("*")):
    if not file.is_file():
        continue
    obj = file.relative_to(STORAGE_ROOT).as_posix()
    client.storage.from_(BUCKET).upload(
        path=obj,
        file=file.read_bytes(),
        file_options={"content-type": content_type(file), "upsert": "true"},
    )
    uploaded += 1
    print(f"[upload] {obj}")
print(f"[upload] {uploaded} file(s) uploaded")


def cdn_url(path: str) -> str:
    return client.storage.from_(BUCKET).get_public_url(path)


# 3) repoint certificate pdf/qr columns at the CDN URLs
from sqlalchemy import text

from app.db.session import engine

prefix = "/api/v1/public/file/"
updated = 0
with engine.begin() as conn:
    rows = conn.execute(text(
        "SELECT id, pdf_url, qr_code_url FROM metricert.certificates"
    )).all()
    for cid, pdf, qr in rows:
        new_pdf = cdn_url(pdf[len(prefix):]) if pdf and pdf.startswith(prefix) else pdf
        new_qr = cdn_url(qr[len(prefix):]) if qr and qr.startswith(prefix) else qr
        conn.execute(
            text("UPDATE metricert.certificates SET pdf_url = :p, qr_code_url = :q WHERE id = :i"),
            {"p": new_pdf, "q": new_qr, "i": cid},
        )
        updated += 1
print(f"[db] repointed {updated} certificate url column(s) to CDN")

print("Done. Existing records now resolve PDFs + QRs from Supabase Storage.")
print("Temporary files can be deleted: " + str(STORAGE_ROOT))