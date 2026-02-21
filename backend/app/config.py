import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-12-01-preview"

    triposr_model_id: str = "stabilityai/TripoSR"
    triposr_device: str = "cuda:0"
    triposr_chunk_size: int = 8192
    triposr_mc_resolution: int = 256
    triposr_texture_resolution: int = 2048
    triposr_foreground_ratio: float = 0.85

    upload_dir: Path = Path("data/uploads")
    output_dir: Path = Path("data/outputs")

    max_upload_size_mb: int = 20
    allowed_extensions: set[str] = {".jpg", ".jpeg", ".png", ".webp"}

    cors_origins: list[str] = ["*"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
