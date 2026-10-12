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

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def sanitize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
    if "postgresql+asyncpg://" in url:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        
        has_ssl = False
        if "sslmode" in query:
            val = query.pop("sslmode")[0]
            if val != "disable":
                has_ssl = True
        if "ssl" in query:
            val = query.pop("ssl")[0]
            if val not in ("0", "false", "disable"):
                has_ssl = True
        else:
            has_ssl = True
            
        allowed = {"statement_cache_size", "command_timeout", "server_settings"}
        new_query = {k: v for k, v in query.items() if k in allowed}
        if has_ssl:
            new_query["ssl"] = ["require"]
            
        new_qs = urlencode(new_query, doseq=True)
        url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_qs, parsed.fragment))
    return url

settings.DATABASE_URL = sanitize_database_url(settings.DATABASE_URL)
