"""App settings, read from the .env file in the project root."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    meta_api_key: str = ""
    meta_api_base_url: str = "https://api.meta.ai/v1"
    text_model: str = "muse-spark-1.3"

    max_upload_mb: int = 16


@lru_cache
def get_settings() -> Settings:
    return Settings()
