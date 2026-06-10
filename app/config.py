from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str = "postgresql+asyncpg://etl:etlpassword@localhost:5432/etl_db"
    app_env: Literal["dev", "prod", "test"] = "dev"
    log_level: str = "INFO"

    # JWT — override JWT_SECRET_KEY with a strong random value in production
    jwt_secret_key: str = "changeme-use-openssl-rand-hex-32-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # API credentials used by POST /auth/token
    api_username: str = "admin"
    api_password: str = "changeme"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
