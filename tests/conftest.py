"""
Shared test fixtures.

Tests never read the developer's real .env, never call paid or external APIs
(unless explicitly marked `live` and opted in), and use a temporary
STORAGE_DIR per test.
"""

import os
import re
import zlib

import numpy as np
import pytest

# Hermetic settings: ignore any .env in the working directory.
from config import settings as settings_module

settings_module.Settings.model_config["env_file"] = None
# Safe defaults for module-level imports (main.py builds an app at import).
os.environ["LLM_PROVIDER"] = "extractive"
os.environ.pop("API_KEY", None)
os.environ.pop("STORAGE_BACKEND", None)

from api import dependencies  # noqa: E402
from persistence import backends  # noqa: E402

DIM = 384
_STOP = {
    "the", "a", "an", "of", "to", "and", "is", "are", "in", "on", "for", "what", "how",
    "do", "does", "i", "my", "our", "with", "be", "can", "it", "this", "that", "by", "at",
    "or", "as", "from", "within", "after", "any", "all",
}


class FakeEmbedder:
    """Deterministic bag-of-words embedder (hashing trick). Offline and fast."""

    model_name = "fake-bow"
    is_loaded = True

    def _vec(self, text: str) -> np.ndarray:
        vec = np.zeros(DIM, dtype=np.float32)
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            if token in _STOP:
                continue
            if len(token) > 4 and token.endswith("s"):
                token = token[:-1]
            vec[zlib.crc32(token.encode()) % DIM] += 1.0
        return vec

    def embed_passages(self, texts):
        if not texts:
            return np.zeros((0, DIM), dtype=np.float32)
        return np.stack([self._vec(t) for t in texts])

    def embed_query(self, query):
        return self._vec(query)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Point all storage at tmp_path and reset cached settings/services."""
    storage = tmp_path / "storage"
    values = {
        "STORAGE_DIR": str(storage),
        "FAISS_INDEX_PATH": str(storage / "faiss_index"),
        "DOCUMENTS_DB_PATH": str(storage / "documents.json"),
        "GOOGLE_CREDENTIALS_PATH": str(tmp_path / "credentials.json"),
        "GOOGLE_TOKEN_PATH": str(tmp_path / "token.json"),
        "GOOGLE_OAUTH_INTERACTIVE": "false",
        "LLM_PROVIDER": "extractive",
        "SIMILARITY_THRESHOLD": "0.2",
        "CHUNK_SIZE": "400",
        "CHUNK_OVERLAP": "60",
        "MIN_CHUNK_SIZE": "80",
        "LOG_LEVEL": "warning",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    for key in ("API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "STORAGE_BACKEND", "GCS_BUCKET",
                "GOOGLE_CREDENTIALS_JSON", "GOOGLE_TOKEN_JSON", "MAX_UPLOAD_MB"):
        monkeypatch.delenv(key, raising=False)

    def reset():
        settings_module.get_settings.cache_clear()
        backends.set_persistence(None)
        dependencies.set_services(None)

    reset()
    settings = settings_module.get_settings()
    settings.ensure_storage_dirs()
    yield monkeypatch
    reset()


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


@pytest.fixture
def make_client(env, fake_embedder):
    """Factory: build services (fake embedder by default) and a TestClient."""
    from fastapi.testclient import TestClient

    import main

    clients = []

    def factory(llm=None, embedder=None, reset_settings=False):
        if reset_settings:
            settings_module.get_settings.cache_clear()
        dependencies.set_services(None)
        services = dependencies.Services(embedder=embedder or fake_embedder, llm=llm)
        dependencies.set_services(services)
        client = TestClient(main.create_app())
        client.__enter__()
        clients.append(client)
        return client, services

    yield factory
    for c in clients:
        c.__exit__(None, None, None)
