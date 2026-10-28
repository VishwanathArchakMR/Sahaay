"""Sahaay Core Configuration and Settings."""

import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with secure defaults."""

    # Server configuration
    host: str = "127.0.0.1"
    port: int = 8000
    environment: str = "development"
    debug: bool = False

    # Security & Authentication
    # Default is auto-generated per-launch token if not explicitly provided
    api_token: str = ""

    # Storage paths
    database_url: str = "sqlite+aiosqlite:///./data/storage/sahaay.db"
    temp_media_dir: Path = Path("./data/temp_media")
    storage_dir: Path = Path("./data/storage")

    # Privacy Gateway Settings
    local_only_mode: bool = True
    strict_consent: bool = True
    log_redaction: bool = True
    hosted_models_permitted: bool = False

    # Meta Hosted Model API Settings
    model_api_key: str = ""
    meta_api_base_url: str = "https://api.meta.ai/v1"
    muse_spark_model_id: str = "muse-spark-1.3"
    muse_wonder_model_id: str = "muse-wonder-1.0"
    muse_voice_model_id: str = "muse-voice-transcribe-1.0"
    sam_model_id: str = "sam-3-1"

    # Meta Muse Image Generation Settings
    meta_image_base_url: str = "https://api.meta.ai/v1"
    muse_image_model: str = "muse-image-1.0"

    # Baseten Model API Settings (Muse Spark Open)
    baseten_base_url: str = "https://inference.baseten.co/v1"
    baseten_api_key: str = ""
    baseten_muse_spark_model: str = "meta-models/muse-spark-open"

    # Visual Storytelling & Task Passport Settings
    enable_visual_storytelling: bool = True
    visual_storytelling_budget: int = 10
    artifacts_dir: Path = Path("./data/artifacts")

    # Local Llama Runtime Settings (Llama 3.2 3B Instruct Q4_K_M GGUF)
    local_llama_model_path: str = ""
    llama_server_path: str = ""
    llama_server_host: str = "127.0.0.1"
    llama_server_port: int = 8080
    local_llama_context_size: int = 4096

    model_config = SettingsConfigDict(
        env_prefix="SAHAAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def initialize_paths_and_tokens(self) -> None:
        """Ensure directories exist and launch token is populated."""
        import os

        self.temp_media_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (self.artifacts_dir / "images").mkdir(parents=True, exist_ok=True)
        if not self.api_token:
            # Generate unguessable 32-byte hex token for this launch
            self.api_token = secrets.token_hex(32)
        if not self.model_api_key:
            self.model_api_key = os.environ.get("MODEL_API_KEY", "")
        if not self.baseten_api_key:
            self.baseten_api_key = os.environ.get("BASETEN_API_KEY", "")


# Global settings singleton
settings = Settings()
settings.initialize_paths_and_tokens()
