from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bayenat API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://bayenat:bayenat@postgres:5432/bayenat"
    redis_url: str = "redis://redis:6379/0"
    storage_root: str = "./storage"
    max_upload_size_bytes: int = 500 * 1024 * 1024
    jwt_secret: str = "change-me-in-development"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_prefix="BAYENAT_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
