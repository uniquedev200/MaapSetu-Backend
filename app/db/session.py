"""Database engine and session management (SQLAlchemy 2.0 style)."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# SQLite (local dev) has no connection pooling and needs check_same_thread=False.
# Postgres/Supabase (production stack): disable driver-level prepared statements so
# pgbouncer transaction-pooling mode (port 5432) never breaks on PREPARE conflicts.
is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {"prepare_threshold": None}

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    **({"pool_size": 5, "max_overflow": 10} if not is_sqlite else {}),
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def session_scope() -> Session:
    """Return a fresh session (used by background/jobs or inline scripts)."""
    return SessionLocal()