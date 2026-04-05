"""Application configuration with environment-based settings."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App mode: "local" or "hosted"
    APP_MODE: str = os.getenv("APP_MODE", "local")

    # Database
    # Local mode: SQLite (default)
    # Hosted mode: PostgreSQL
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./kickboxing_tournament.db"
    )

    # Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-use-a-real-secret")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    STAFF_PASSWORD: str = os.getenv("STAFF_PASSWORD", "staff123")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours for tournament day

    # Sync (local -> hosted)
    SYNC_TARGET_URL: str = os.getenv("SYNC_TARGET_URL", "")
    SYNC_API_KEY: str = os.getenv("SYNC_API_KEY", "")

    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
