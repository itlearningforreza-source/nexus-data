from __future__ import annotations

import os
import secrets
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _generate_secret(length: int = 32) -> str:
    """Generate a cryptographically secure random secret."""
    return secrets.token_urlsafe(length)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Nexus Data"
    ENV: str = "development"
    DEBUG: bool = True

    # Default to PostgreSQL for Docker, fallback to SQLite for local dev
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'nexus.db'}")
    # SECURITY: No default secrets - generate secure random if not provided
    SECRET_KEY: str = os.getenv("SECRET_KEY", _generate_secret(48))
    JWT_SECRET: str = os.getenv("JWT_SECRET", _generate_secret(48))
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    STORAGE_PATH: str = os.getenv("STORAGE_PATH", str(BASE_DIR / "storage"))
    CACHE_PATH: str = os.getenv("CACHE_PATH", str(BASE_DIR / "cache"))
    EXPORT_PATH: str = os.getenv("EXPORT_PATH", str(BASE_DIR / "exports"))

    MAX_UPLOAD_MB: int = 200
    PASSWORD_MIN_LENGTH: int = 8

    AI_API_KEY: str | None = os.getenv("AI_API_KEY")
    AI_BASE_URL: str | None = os.getenv("AI_BASE_URL")
    AI_MODEL: str = os.getenv("AI_MODEL", "gpt-4o-mini")
    AI_ENABLED: bool = bool(os.getenv("AI_API_KEY") and os.getenv("AI_BASE_URL"))

    WORKER_INLINE: bool = os.getenv("WORKER_INLINE", "true").lower() == "true"
    # SECURITY: CORS_ORIGINS must be explicitly configured in production
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_MAX: int = 200
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    AUDIT_ENABLED: bool = True

    # Security headers
    CSP_ENABLED: bool = True

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def storage_dir(self) -> Path:
        return Path(self.STORAGE_PATH)

    @property
    def cache_dir(self) -> Path:
        return Path(self.CACHE_PATH)

    @property
    def export_dir(self) -> Path:
        path = Path(self.EXPORT_PATH)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_dirs(self) -> None:
        for d in (self.storage_dir, self.cache_dir, self.export_dir):
            d.mkdir(parents=True, exist_ok=True)

    def validate_production(self) -> list[str]:
        """Validate settings for production deployment."""
        warnings = []
        if self.ENV == "production":
            if self.DEBUG:
                warnings.append("DEBUG should be False in production")
            if self.CORS_ORIGINS == "*":
                warnings.append("CORS_ORIGINS should not be wildcard in production")
        return warnings


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


settings = get_settings()