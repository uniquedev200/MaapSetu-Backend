"""Application configuration loaded from environment variables (.env)."""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings.

    All values can be overridden via environment variables or a ``.env`` file.
    Sensible local-development defaults are provided so the application is
    immediately runnable with zero configuration (SQLite + local storage).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General --------------------------------------------------------
    PROJECT_NAME: str = "MetriCert"
    PROJECT_DESCRIPTION: str = (
        "Unified Legal Metrology Verification & Lifecycle Management System"
    )
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # --- Security -------------------------------------------------------
    SECRET_KEY: str = "change-me-in-production-please-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_SCHEME: str = "pbkdf2_sha256"
    PASSWORD_ROUNDS: int = 290_000
    BCRYPT_ERROR_NOTE: str = ""  # reserved / not used

    # --- Database -------------------------------------------------------
    # PostgreSQL. Must be provided per-environment (set DATABASE_URL env var).
    # The demo/dev default points at Supabase and is overridden in deployment.
    DATABASE_URL: str = "postgresql+psycopg://YOUR_USER:YOUR_PASSWORD@YOUR_HOST:5432/postgres"
    DB_ECHO: bool = False

    # --- Public consumer portal -----------------------------------------
    # Origin of the public "verify by QR" webpage. Certificate QR codes encode
    # ``{PUBLIC_BASE_URL}/verify/{certificate_id}`` which renders a structured,
    # consumer-facing verification page (never raw JSON).
    PUBLIC_BASE_URL: str = "http://localhost:5175"

    # --- CORS -----------------------------------------------------------
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:8000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    CORS_ALLOW_CREDENTIALS: bool = False
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # --- Storage --------------------------------------------------------
    # backends: "local" | "supabase"
    STORAGE_BACKEND: str = "local"
    STORAGE_BASE_URL: str = "/api/v1/public/file"
    UPLOAD_DIR: str = "./storage"
    PUBLIC_MAX_FILE_AGE_DAYS: int = 30

    # Supabase storage (only required when STORAGE_BACKEND == "supabase")
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "metricert"

    # --- AI assistant ---------------------------------------------------
    # Optional GROQ API key for the BUSINESS onboarding helper. When unset,
    # /api/v1/assistant/chat answers from a local knowledge base instead.
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_API_BASE: str = "https://api.groq.com/openai/v1"

    # --- Blockchain -----------------------------------------------------
    BLOCKCHAIN_IMPLEMENTATION: str = "embedded"  # embedded | hyperledger | polygon | ethereum
    BLOCKCHAIN_PROOF_OF_WORK: bool = False
    BLOCKCHAIN_DIFFICULTY: int = 3

    # --- Certificate ----------------------------------------------------
    CERTIFICATE_VALIDITY_MONTHS: int = 12
    CERTIFICATE_EXPIRY_WARNING_DAYS: int = 30
    OFFICIAL_AUTHORITY_NAME: str = "Metrology Authority of Standards & Measures"
    OFFICIAL_OATH: str = "This is to certify that the instrument described below has been verified in accordance with the provisions of the Legal Metrology Act, 2009 and the rules made thereunder."
    ISSUING_OFFICER_TITLE: str = "Chief Inspector, Legal Metrology"

    # --- Seed -----------------------------------------------------------
    SEED_ADMIN_EMAIL: str = "admin@metricert.gov.in"
    SEED_ADMIN_PASSWORD: str = "admin12345"
    SEED_ADMIN_PHONE: str = "9000000000"
    SEED_ON_STARTUP: bool = True
    SEED_DEMO_USERS: bool = True  # demo LMO/GATC/BUSINESS accounts used by the demo & E2E

    # --- Logging --------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod"}

    @property
    def secret_key(self) -> str:
        if self.is_production and self.SECRET_KEY == "change-me-in-production-please-use-a-long-random-string":
            raise RuntimeError(
                "SECRET_KEY must be overridden in production via environment variables."
            )
        return self.SECRET_KEY


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor for dependency injection."""
    return Settings()