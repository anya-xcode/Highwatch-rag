"""
Centralized configuration management using Pydantic Settings.
All environment variables are loaded and validated here.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Google Drive ---
    google_credentials_path: str = "credentials.json"
    google_token_path: str = "token.json"
    google_drive_folder_ids: str = ""

    # --- LLM ---
    llm_provider: str = "openai"  # "openai" or "gemini"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.1-70b-versatile"

    # --- Embedding ---
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 64
    embedding_dimension: int = 384

    # --- Chunking ---
    chunk_size: int = 512
    chunk_overlap: int = 64
    min_chunk_size: int = 50

    # --- Search ---
    top_k_results: int = 5
    similarity_threshold: float = 0.3

    # --- Storage ---
    storage_dir: str = "./storage"
    faiss_index_path: str = "./storage/faiss_index"
    documents_db_path: str = "./storage/documents.json"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    @property
    def folder_ids(self) -> list[str]:
        """Parse comma-separated folder IDs."""
        if not self.google_drive_folder_ids:
            return []
        return [fid.strip() for fid in self.google_drive_folder_ids.split(",") if fid.strip()]

    def ensure_storage_dirs(self) -> None:
        """Create storage directories if they don't exist."""
        Path(self.storage_dir).mkdir(parents=True, exist_ok=True)
        Path(self.faiss_index_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_storage_dirs()
    return settings
