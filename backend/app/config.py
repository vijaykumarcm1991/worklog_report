"""Application configuration."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Worklog Dashboard"
    database_url: str = "sqlite:///./data/worklog.db"
    # Fernet key used to encrypt instance credentials at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    enc_key: str = Field(default="", validation_alias="WORKLOG_ENC_KEY")
    sync_interval_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    default_daily_hours: float = 8.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
