"""Sahaay Core Configuration and Settings."""

import secrets
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Determine repository root reliably across any working directory or runner checkout
def find_repo_root() -> Path:
    """Find the repository root by locating marker files/directories."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "core" / "src" / "sahaay_core").exists() and (parent / "data").exists():
            return parent
    cwd = Path.cwd()
    if (cwd / "core" / "src" / "sahaay_core").exists() and (cwd / "data").exists():
        return cwd
    if (cwd / "data" / "fixtures").exists():
        return cwd
    return Path(__file__).resolve().parents[4]


REPO_ROOT = find_repo_root()


def get_repo_root() -> Path:
    """Return the authoritative repository root Path."""
    return REPO_ROOT


def get_fixtures_dir() -> Path:
    """Return the authoritative fixtures directory Path."""
    primary = REPO_ROOT / "data" / "fixtures"
    if primary.exists():
        return primary
    cwd_path = Path.cwd() / "data" / "fixtures"
    if cwd_path.exists():
        return cwd_path
    return primary


def get_fixture_path(relative_name: str) -> Path:
    """Return the resolved Path for a named fixture file."""
    clean_name = relative_name.replace("\\", "/")
    if clean_name.startswith("data/fixtures/"):
        clean_name = clean_name[len("data/fixtures/") :]
    elif clean_name.startswith("/data/fixtures/"):
        clean_name = clean_name[len("/data/fixtures/") :]
    elif clean_name.startswith("data/"):
        clean_name = clean_name[len("data/") :]

    return get_fixtures_dir() / clean_name


class Settings(BaseSettings):
    """Application settings with secure defaults."""

    # Server configuration
    host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("SAHAAY_HOST", "HOST"),
    )
    port: int = Field(
        default=8000,
        validation_alias=AliasChoices("SAHAAY_PORT", "PORT"),
    )
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("SAHAAY_ENVIRONMENT", "ENVIRONMENT"),
    )
    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("SAHAAY_DEBUG", "DEBUG"),
    )

    # Security & Authentication
    api_token: str = Field(
        default="",
        validation_alias=AliasChoices("SAHAAY_API_TOKEN", "API_TOKEN"),
    )

    # Storage paths
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/storage/sahaay.db",
        validation_alias=AliasChoices("SAHAAY_DATABASE_URL", "DATABASE_URL"),
    )
    temp_media_dir: Path = REPO_ROOT / "data" / "temp_media"
    storage_dir: Path = REPO_ROOT / "data" / "storage"

    # Privacy Gateway Settings
    local_only_mode: bool = Field(
        default=True,
        validation_alias=AliasChoices("SAHAAY_PRIVACY_LOCAL_ONLY_MODE", "LOCAL_ONLY_MODE"),
    )
    strict_consent: bool = Field(
        default=True,
        validation_alias=AliasChoices("SAHAAY_PRIVACY_STRICT_CONSENT", "STRICT_CONSENT"),
    )
    log_redaction: bool = Field(
        default=True,
        validation_alias=AliasChoices("SAHAAY_PRIVACY_LOG_REDACTION", "LOG_REDACTION"),
    )
    hosted_models_permitted: bool = False

    # Meta Hosted Model API Settings
    model_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SAHAAY_MODEL_API_KEY", "MODEL_API_KEY", "META_LLAMA_API_KEY"
        ),
    )
    meta_api_base_url: str = Field(
        default="https://api.meta.ai/v1",
        validation_alias=AliasChoices("SAHAAY_META_API_BASE_URL", "META_API_BASE_URL"),
    )
    muse_spark_model_id: str = Field(
        default="muse-spark-1.3",
        validation_alias=AliasChoices("SAHAAY_MUSE_SPARK_MODEL_ID", "MUSE_SPARK_MODEL_ID"),
    )
    muse_wonder_model_id: str = Field(
        default="muse-wonder-1.0",
        validation_alias=AliasChoices("SAHAAY_MUSE_WONDER_MODEL_ID", "MUSE_WONDER_MODEL_ID"),
    )
    muse_voice_model_id: str = Field(
        default="muse-voice-transcribe-1.0",
        validation_alias=AliasChoices("SAHAAY_MUSE_VOICE_MODEL_ID", "MUSE_VOICE_MODEL_ID"),
    )
    sam_model_id: str = Field(
        default="sam-3.1",
        validation_alias=AliasChoices("SAHAAY_SAM_MODEL_ID", "SAM_MODEL_ID"),
    )

    # Meta Muse Image Generation Settings
    meta_image_base_url: str = Field(
        default="https://api.meta.ai/v1",
        validation_alias=AliasChoices("SAHAAY_META_IMAGE_BASE_URL", "META_IMAGE_BASE_URL"),
    )
    muse_image_model: str = Field(
        default="muse-image-1.0",
        validation_alias=AliasChoices("SAHAAY_MUSE_IMAGE_MODEL", "MUSE_IMAGE_MODEL"),
    )

    # Visual Storytelling & Task Passport Settings
    enable_visual_storytelling: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "SAHAAY_ENABLE_VISUAL_STORYTELLING", "ENABLE_VISUAL_STORYTELLING"
        ),
    )
    visual_storytelling_budget: int = Field(
        default=10,
        validation_alias=AliasChoices(
            "SAHAAY_VISUAL_STORYTELLING_BUDGET", "VISUAL_STORYTELLING_BUDGET"
        ),
    )
    artifacts_dir: Path = REPO_ROOT / "data" / "artifacts"

    # Local Llama Runtime Settings (Llama 3.2 3B Instruct Q4_K_M GGUF)
    local_llama_model_path: str = ""
    llama_server_path: str = ""
    llama_server_host: str = "127.0.0.1"
    llama_server_port: int = 8080
    local_llama_context_size: int = 4096

    # Internet Research Settings
    enable_web_research: bool = Field(
        default=True,
        validation_alias=AliasChoices("SAHAAY_ENABLE_WEB_RESEARCH", "ENABLE_WEB_RESEARCH"),
    )
    web_research_max_results: int = 5
    web_fetch_timeout_seconds: float = 10.0
    web_fetch_max_size_bytes: int = 2 * 1024 * 1024  # 2MB

    model_config = SettingsConfigDict(
        env_prefix="SAHAAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def async_database_url(self) -> str:
        """Returns a normalized sqlite+aiosqlite database URL with an absolute path."""
        url = self.database_url.strip()
        if url.startswith("sqlite+aiosqlite:///"):
            raw_path = url[len("sqlite+aiosqlite:///") :]
            if not Path(raw_path).is_absolute():
                abs_path = (REPO_ROOT / raw_path).resolve()
                return f"sqlite+aiosqlite:///{abs_path.as_posix()}"
            return url
        if url.startswith("sqlite:///"):
            raw_path = url[len("sqlite:///") :]
            if not Path(raw_path).is_absolute():
                abs_path = (REPO_ROOT / raw_path).resolve()
                return f"sqlite+aiosqlite:///{abs_path.as_posix()}"
            return f"sqlite+aiosqlite:///{Path(raw_path).resolve().as_posix()}"
        return url

    @property
    def sync_database_path(self) -> Path:
        """Returns the local filesystem path to the SQLite database file."""
        url = self.database_url.strip()
        prefix = "sqlite+aiosqlite:///" if url.startswith("sqlite+aiosqlite:///") else "sqlite:///"
        if url.startswith(prefix):
            raw_path = url[len(prefix) :]
            if not Path(raw_path).is_absolute():
                return (REPO_ROOT / raw_path).resolve()
            return Path(raw_path).resolve()
        return (self.storage_dir / "sahaay.db").resolve()

    @property
    def repo_root(self) -> Path:
        """Returns the canonical repository root path."""
        return REPO_ROOT

    def initialize_paths_and_tokens(self) -> None:
        """Ensure directories exist and launch token is populated."""
        import os

        self.temp_media_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (self.artifacts_dir / "images").mkdir(parents=True, exist_ok=True)
        self.sync_database_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.api_token:
            # Generate unguessable 32-byte hex token for this launch
            self.api_token = secrets.token_hex(32)
        if not self.model_api_key:
            self.model_api_key = os.environ.get(
                "MODEL_API_KEY", os.environ.get("META_LLAMA_API_KEY", "")
            )


# Global settings singleton
settings = Settings()
settings.initialize_paths_and_tokens()
