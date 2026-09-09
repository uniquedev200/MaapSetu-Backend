"""MetriCert FastAPI application entrypoint.

Run locally with::

    uvicorn app.main:app --reload --port 8000

Bootstraps the database tables, seeds the default admin account and the
blockchain genesis block, then exposes the v1 API under ``/api/v1``.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.models  # noqa: F401  (must import model modules so metadata is populated)
from app.api.v1.router import api_router
from app.auth.security import hash_password  # noqa: F401
from app.blockchain.service import BlockchainService
from app.core.config import get_settings
from app.core.enums import UserRole, UserStatus
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.utils.id_generator import user_id

settings = get_settings()
configure_logging()


@asynccontextmanager
async def _lifespan(application: FastAPI):
    _on_startup()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        lifespan=_lifespan,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    application.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        from app.middleware.request_context import new_request_id, set_request_id

        set_request_id(new_request_id())
        return await call_next(request)

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
            headers={"X-Error-Code": exc.code},
        )

    @application.get("/", include_in_schema=False)
    def root():
        return {"name": settings.PROJECT_NAME, "version": settings.VERSION, "docs": "/api/v1/docs"}

    @application.get("/health", tags=["System"])
    def health():
        return {"status": "ok", "environment": settings.ENVIRONMENT}

    return application


def _seed_admin() -> None:
    """Create the default administrator account on first boot (idempotent)."""
    repo = UserRepository(SessionLocal())
    email = settings.SEED_ADMIN_EMAIL
    if repo.get_by_email(email):
        return
    repo.create(
        public_id=user_id(),
        name="System Administrator",
        email=email,
        password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
        phone=settings.SEED_ADMIN_PHONE,
        role=UserRole.ADMIN.value,
        status=UserStatus.ACTIVE.value,
        settings={"notifications": {"email": True, "sms": False}, "two_factor_auth": False, "theme": "light"},
    )


_DEMO_USERS = [
    # (email, name, role, district, business_name, address)
    ("guptat311227@example.com", "S. Gupta", UserRole.LMO.value, "Pune", None, None),
    ("anilv311227@example.com", "Anil Verma", UserRole.LMO.value, "Pune", None, None),
    ("divyan311227@example.com", "Divya Nair", UserRole.GATC.value, "Mumbai", None, None),
    ("acmet311227@example.com", "Acme Tech", UserRole.BUSINESS.value, "Pune",
     "Acme Inventory Solutions", "Sector 18, Hadapsar Industrial Estate, Pune, Maharashtra 411028"),
]


def _seed_demo_users() -> None:
    """Create the demo LMO/GATC/BUSINESS accounts used in demos & E2E (idempotent)."""
    repo = UserRepository(SessionLocal())
    for email, name, role, district, business_name, address in _DEMO_USERS:
        if repo.get_by_email(email):
            continue
        repo.create(
            public_id=user_id(),
            name=name,
            email=email,
            password_hash=hash_password("secret123"),
            phone="9000000001",
            role=role,
            status=UserStatus.ACTIVE.value,
            district=district,
            business_name=business_name,
            address=address,
            settings={"notifications": {"email": True, "sms": False}, "two_factor_auth": False, "theme": "light"},
        )


def _ensure_columns(engine) -> None:
    """Idempotent column migrations for pre-existing tables.

    ``Base.metadata.create_all`` only creates missing *tables*, so new columns
    on existing tables must be added explicitly (Postgres: ``IF NOT EXISTS``;
    SQLite: tolerate the duplicate-column error).
    """
    from sqlalchemy import text

    migrations = [
        ("instruments", "is_active BOOLEAN NOT NULL DEFAULT TRUE"),
    ]
    with engine.begin() as conn:
        for table, column in migrations:
            if conn.dialect.name == "postgresql":
                conn.execute(text(f'ALTER TABLE metricert.{table} ADD COLUMN IF NOT EXISTS {column}'))
            else:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column}"))
                except Exception:
                    pass


def _on_startup() -> None:
    # Ensure our app schema exists before create_all (PostgreSQL stacks).
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS metricert"))
    Base.metadata.create_all(bind=engine)
    _ensure_columns(engine)
    if settings.SEED_ON_STARTUP:
        _seed_admin()
        if settings.SEED_DEMO_USERS:
            _seed_demo_users()
    BlockchainService(SessionLocal()).ensure_genesis()


app = create_app()