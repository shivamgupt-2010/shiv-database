import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for SHIV Database V1."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # General Settings
    APP_NAME: str = "SHIV Database V1"
    SERVICE_NAME: str = "shiv-database"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./shiv_dev.db"
    DB_ECHO: bool = False

    # Security & Auth Settings
    JWT_SECRET_KEY: str = "shiv-platform-super-secret-jwt-key-for-local-dev-12345"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # API Key Configuration
    API_KEY_PREFIX: str = "shiv_sk_"

    # Rate Limiting Settings
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 100
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10

    # CORS Settings
    ALLOWED_ORIGINS: List[str] = ["*"]

    # External Provider Credentials
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None


settings = Settings()

# Ensure we always use the asyncpg driver for PostgreSQL
if settings.DATABASE_URL.startswith("postgres://"):
    settings.DATABASE_URL = settings.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif settings.DATABASE_URL.startswith("postgresql://"):
    settings.DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
