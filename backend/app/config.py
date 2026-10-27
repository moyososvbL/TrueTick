"""App settings, read from the .env file in the project root."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    meta_api_key: str = ""
    meta_api_base_url: str = "https://api.meta.ai/v1"
    text_model: str = "muse-spark-1.3"
    vision_model: str = "muse-spark-1.3"
    segment_model: str = "sam-3.1"
    transcribe_model: str = "muse-voice-transcribe-1.0"
    image_model: str = "muse-image-1.0"

    max_upload_mb: int = 16
    data_dir: str = "data"  # local SQLite for community reports (no message content stored)


@lru_cache
def get_settings() -> Settings:
    return Settings()
