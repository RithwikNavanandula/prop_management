from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os


class Settings(BaseSettings):
    # Default to SQLite for easy local development, override via .env
    DATABASE_URL: str = "sqlite:///./property_mgmt.db"
    SECRET_KEY: str = "your-super-secret-jwt-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ALGORITHM: str = "HS256"
    UPLOAD_DIR: str = "uploads"
    QR_CODE_DIR: str = "static/qrcodes"
    APP_NAME: str = "PropManager Pro"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # SMTP Settings
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@propmgr.com"
    SMTP_FROM_NAME: str = "PropManager Pro"
    SMTP_TLS: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
