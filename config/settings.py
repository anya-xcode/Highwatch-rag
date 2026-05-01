"""
Centralized configuration management using Pydantic Settings.
All environment variables are loaded and validated here.
"""

import os
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


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
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", env="EMBEDDING_MODEL")
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
        """Create storage directories and reconstruct credentials/tokens from environment."""
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Cloud Deployment Helper: Reconstruct credentials.json from Environment Variable
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json and not os.path.exists(self.google_credentials_path):
            try:
                json_data = json.loads(creds_json)
                with open(self.google_credentials_path, "w") as f:
                    json.dump(json_data, f, indent=2)
                print(f"✅ Reconstructed credentials from environment")
            except Exception as e:
                print(f"❌ Failed to reconstruct credentials: {e}")

        # Cloud Deployment Helper: Reconstruct token.json from Environment Variable
        token_json = os.environ.get("GOOGLE_TOKEN_JSON")
        if token_json and not os.path.exists(self.google_token_path):
            try:
                token_data = json.loads(token_json)
                with open(self.google_token_path, "w") as f:
                    json.dump(token_data, f, indent=2)
                print(f"✅ Reconstructed OAuth token from environment")
            except Exception as e:
                print(f"❌ Failed to reconstruct token: {e}")
        
        Path(self.faiss_index_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_storage_dirs()
    return settings
