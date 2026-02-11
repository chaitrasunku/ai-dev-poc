import os
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Petstore API"
    ENVIRONMENT: str = "development" # development, staging, production
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/petstore"

    SECRET_KEY: str = secrets.token_urlsafe(32) # Generate a strong default
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # Testing database URL, separate from main DATABASE_URL for integration tests
    TEST_DATABASE_URL: str = "postgresql+asyncpg://test_user:test_password@localhost:5433/test_petstore"

    # Ensure DEBUG is False for production
    if os.getenv("ENVIRONMENT") == "production":
        DEBUG = False

settings = Settings()