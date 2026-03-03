import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-12-01-preview"

    # TripoSR (legacy MVP)
    triposr_model_id: str = "stabilityai/TripoSR"
    triposr_device: str = "cuda:0"
    triposr_chunk_size: int = 8192
    triposr_mc_resolution: int = 256
    triposr_texture_resolution: int = 2048
    triposr_foreground_ratio: float = 0.85

    # File paths
    upload_dir: Path = Path("data/uploads")
    output_dir: Path = Path("data/outputs")

    max_upload_size_mb: int = 500
    allowed_extensions: set[str] = {".jpg", ".jpeg", ".png", ".webp"}
    allowed_video_extensions: set[str] = {".mp4", ".mov", ".avi"}

    cors_origins: list[str] = ["*"]

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/insurascan"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # Azure Blob Storage
    azure_blob_connection_string: str = ""
    azure_blob_container_name: str = "insurascan-storage"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
