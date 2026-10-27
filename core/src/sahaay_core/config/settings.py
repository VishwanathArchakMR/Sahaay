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

    model_config = SettingsConfigDict(
        env_prefix="SAHAAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def initialize_paths_and_tokens(self) -> None:
        """Ensure directories exist and launch token is populated."""
        self.temp_media_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        if not self.api_token:
            # Generate unguessable 32-byte hex token for this launch
            self.api_token = secrets.token_hex(32)


# Global settings singleton
settings = Settings()
settings.initialize_paths_and_tokens()
