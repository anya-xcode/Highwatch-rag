"""
Centralized configuration management using Pydantic Settings.
All environment variables are loaded and validated here.

Budget rule: only providers/services with a genuinely free option are
supported. Paid-only providers (e.g. OpenAI) are rejected at startup so the
app can never silently fall back to a paid API.
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import structlog
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)

APP_VERSION = "2.0.0"

# Providers with a free option. "extractive" uses no LLM at all.
SUPPORTED_LLM_PROVIDERS = ("groq", "gemini", "extractive")
PAID_ONLY_PROVIDERS = ("openai",)

# Legacy .doc (binary Word) cannot be parsed by python-docx, so it is not listed.
DEFAULT_ALLOWED_EXTENSIONS = ".pdf,.docx,.txt,.md"


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Old .env files may still contain removed keys (e.g. OPENAI_API_KEY).
        extra="ignore",
    )

    # --- Google Drive ---
    google_credentials_path: str = "credentials.json"
    google_token_path: str = "token.json"
    google_drive_folder_ids: str = ""
    # Allow opening a browser for the OAuth consent flow. Must be false on
    # servers/containers (there is no browser there).
    google_oauth_interactive: bool = True
    drive_max_file_mb: int = 25
    auto_sync_on_startup: bool = False

    # --- LLM ---
    llm_provider: str = "groq"
    groq_api_key: Optional[str] = None
    groq_model: str = "openai/gpt-oss-120b"
    # Only sent to reasoning models (gpt-oss). "low" saves free-tier tokens.
    groq_reasoning_effort: Optional[str] = "low"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3.5-flash-lite"
    llm_temperature: float = 0.2
    llm_max_output_tokens: int = 1024
    llm_timeout_seconds: float = 60.0

    # --- Embedding ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_batch_size: int = 64
    embedding_dimension: int = 384
    # Where FastEmbed caches model files (baked into the Docker image).
    embedding_cache_dir: Optional[str] = None
    # Prepended to questions before embedding. Unset = automatic (the official
    # BGE retrieval instruction for BGE English models); empty string = none.
    embedding_query_prefix: Optional[str] = None

    # --- Chunking (characters) ---
    chunk_size: int = 1000
    chunk_overlap: int = 150
    min_chunk_size: int = 200

    # --- Search ---
    top_k_results: int = 5
    # Calibrated on bge-small-en-v1.5 (with query instruction): related questions
    # scored >= 0.685, unrelated ones <= 0.44. Pinned by an integration test.
    similarity_threshold: float = 0.55

    # --- Storage ---
    storage_dir: str = "./storage"
    faiss_index_path: str = "./storage/faiss_index"
    documents_db_path: str = "./storage/documents.json"
    # "local" (default, $0) or "gcs" (requires a billing-enabled GCP project).
    storage_backend: Literal["local", "gcs"] = "local"
    gcs_bucket: Optional[str] = None
    gcs_prefix: str = "highwatch-rag"

    # --- Uploads ---
    max_upload_mb: int = 10
    allowed_extensions: str = DEFAULT_ALLOWED_EXTENSIONS

    # --- Security ---
    # When set, every endpoint except health/config requires X-API-Key.
    api_key: Optional[str] = None
    # Comma-separated origins. Empty = no CORS (the bundled UI is same-origin).
    cors_origins: str = ""

    # --- Server / logging ---
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    log_format: Literal["console", "json"] = "console"

    # ── Validators ─────────────────────────────────────────

    @field_validator("llm_provider")
    @classmethod
    def _validate_provider(cls, value: str) -> str:
        provider = (value or "").strip().lower()
        if provider in PAID_ONLY_PROVIDERS:
            raise ValueError(
                f"LLM_PROVIDER '{provider}' is a paid API and is not supported "
                f"(this project has a $0 budget). Use one of: {', '.join(SUPPORTED_LLM_PROVIDERS)}."
            )
        if provider not in SUPPORTED_LLM_PROVIDERS:
            raise ValueError(
                f"Unknown LLM_PROVIDER '{value}'. Use one of: {', '.join(SUPPORTED_LLM_PROVIDERS)}."
            )
        return provider

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        level = (value or "info").strip().lower()
        if level not in {"debug", "info", "warning", "error", "critical"}:
            raise ValueError("LOG_LEVEL must be debug, info, warning, error or critical")
        return level

    @field_validator("groq_api_key", "gemini_api_key", "api_key", "gcs_bucket", mode="before")
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    # ── Derived values ─────────────────────────────────────

    @property
    def folder_ids(self) -> list[str]:
        """Parse comma-separated folder IDs."""
        if not self.google_drive_folder_ids:
            return []
        return [fid.strip() for fid in self.google_drive_folder_ids.split(",") if fid.strip()]

    @property
    def allowed_extension_set(self) -> set[str]:
        exts = set()
        for ext in self.allowed_extensions.split(","):
            ext = ext.strip().lower()
            if ext:
                exts.add(ext if ext.startswith(".") else f".{ext}")
        return exts

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def drive_max_file_bytes(self) -> int:
        return self.drive_max_file_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def uploads_dir(self) -> Path:
        return Path(self.storage_dir) / "uploads"

    @property
    def downloads_dir(self) -> Path:
        return Path(self.storage_dir) / "downloads"

    @property
    def sync_state_path(self) -> Path:
        return Path(self.storage_dir) / "sync_state.json"

    @property
    def llm_model(self) -> Optional[str]:
        return {
            "groq": self.groq_model,
            "gemini": self.gemini_model,
            "extractive": None,
        }.get(self.llm_provider)

    def ensure_storage_dirs(self) -> None:
        """Create storage directories and reconstruct Google credentials from env vars."""
        os.makedirs(self.storage_dir, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        Path(self.faiss_index_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.documents_db_path).parent.mkdir(parents=True, exist_ok=True)

        # Cloud deployment helper: hosts without a file system for secrets can
        # pass credentials.json / token.json contents as environment variables.
        _write_json_from_env("GOOGLE_CREDENTIALS_JSON", self.google_credentials_path)
        _write_json_from_env("GOOGLE_TOKEN_JSON", self.google_token_path)


def _write_json_from_env(env_name: str, path: str) -> None:
    raw = os.environ.get(env_name)
    if not raw or os.path.exists(path):
        return
    try:
        data = json.loads(raw)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # Owner-only permissions: these files contain OAuth secrets.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Reconstructed file from environment", env=env_name, path=path)
    except Exception as e:  # noqa: BLE001 - never crash startup on this helper
        logger.error("Failed to reconstruct file from environment", env=env_name, error=str(e))


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
