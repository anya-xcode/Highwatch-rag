"""
Service container and request dependencies.

All long-lived services (vector store, registry, models, LLM client) are
created once per process and shared. Tests replace them with set_services().
"""

import secrets
import threading
from typing import Optional

from fastapi import Header, HTTPException, status

from api.llm_service import LLMService
from config.settings import Settings, get_settings
from connectors.gdrive import GoogleDriveConnector
from embedding.embedder import EmbeddingService
from persistence.backends import get_persistence
from processing.chunker import TextChunker
from processing.parser import DocumentParser
from processing.pipeline import IngestionPipeline
from processing.registry import DocumentRegistry
from search.vector_store import VectorStore


class Services:
    """Holds the application's shared services."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        embedder=None,
        store: Optional[VectorStore] = None,
        registry: Optional[DocumentRegistry] = None,
        llm: Optional[LLMService] = None,
        gdrive: Optional[GoogleDriveConnector] = None,
    ):
        self.settings = settings or get_settings()
        self.persistence = get_persistence()
        self.parser = DocumentParser()
        self.chunker = TextChunker()
        self.embedder = embedder or EmbeddingService()
        self.store = store or VectorStore(persistence=self.persistence)
        self.registry = registry or DocumentRegistry(self.settings.documents_db_path, persistence=self.persistence)
        self.llm = llm or LLMService(self.settings)
        self._gdrive = gdrive
        self.pipeline = IngestionPipeline(self.parser, self.chunker, self.embedder, self.store, self.registry)
        self.sync_lock = threading.Lock()

    @property
    def gdrive(self) -> GoogleDriveConnector:
        if self._gdrive is None:
            self._gdrive = GoogleDriveConnector(self.settings, persistence=self.persistence)
        return self._gdrive


_services: Optional[Services] = None
_services_lock = threading.Lock()


def get_services() -> Services:
    global _services
    if _services is None:
        with _services_lock:
            if _services is None:
                _services = Services()
    return _services


def set_services(services: Optional[Services]) -> None:
    """Replace (or reset with None) the shared services. Used by tests."""
    global _services
    _services = services


def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    """Enforce the X-API-Key header when API_KEY is configured."""
    expected = get_settings().api_key
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key. Send it in the X-API-Key header.",
            headers={"WWW-Authenticate": "API-Key"},
        )
