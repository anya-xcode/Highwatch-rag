"""
Embedding Service
Generates vector embeddings locally with FastEmbed (ONNX, CPU, no API cost).

Documents are embedded with `passage_embed` and questions with `query_embed`,
which lets models that distinguish the two (such as BGE) retrieve better.
"""

import hashlib
import threading
from typing import List, Optional

import numpy as np
import structlog
from cachetools import LRUCache

from config.settings import get_settings

logger = structlog.get_logger(__name__)

# Process-wide cache keyed by (kind, sha256(text)).
_embedding_cache: LRUCache = LRUCache(maxsize=10000)
_cache_lock = threading.Lock()

# Recommended by the BGE authors for short-query → passage retrieval. FastEmbed's
# query_embed() does not add it for BGE models; measured on our test set it widens
# the related/unrelated score gap from 0.21 to 0.25.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


def default_query_prefix(model_name: str) -> str:
    name = model_name.lower()
    return BGE_QUERY_INSTRUCTION if "bge" in name and "-en" in name else ""


def _key(kind: str, text: str) -> tuple[str, str]:
    return kind, hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingService:
    """Generates embeddings using FastEmbed models."""

    def __init__(self, model_name: Optional[str] = None, cache_dir: Optional[str] = None):
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.batch_size = settings.embedding_batch_size
        self.cache_dir = cache_dir or settings.embedding_cache_dir
        # None = automatic (BGE instruction for BGE English models); "" = none.
        self.query_prefix = (
            settings.embedding_query_prefix
            if settings.embedding_query_prefix is not None
            else default_query_prefix(self.model_name)
        )
        self._model = None
        self._load_lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def model(self):
        """Lazy-load the embedding model (downloaded once, then cached on disk)."""
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    from fastembed import TextEmbedding

                    logger.info("Loading embedding model", model=self.model_name, cache_dir=self.cache_dir)
                    kwargs = {"model_name": self.model_name}
                    if self.cache_dir:
                        kwargs["cache_dir"] = self.cache_dir
                    self._model = TextEmbedding(**kwargs)
                    logger.info("Embedding model loaded", model=self.model_name)
        return self._model

    def embed_passages(self, texts: List[str]) -> np.ndarray:
        """Embed document chunks. Returns a (len(texts), dim) float32 array."""
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)

        results: dict[int, np.ndarray] = {}
        missing_idx, missing_text = [], []
        with _cache_lock:
            for i, text in enumerate(texts):
                cached = _embedding_cache.get(_key("passage", text))
                if cached is not None:
                    results[i] = cached
                else:
                    missing_idx.append(i)
                    missing_text.append(text)

        if missing_text:
            logger.info("Embedding passages", total=len(texts), to_encode=len(missing_text))
            new = list(self.model.passage_embed(missing_text, batch_size=self.batch_size))
            with _cache_lock:
                for i, text, emb in zip(missing_idx, missing_text, new):
                    vec = np.asarray(emb, dtype=np.float32)
                    _embedding_cache[_key("passage", text)] = vec
                    results[i] = vec

        return np.stack([results[i] for i in range(len(texts))]).astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a search query. Returns a (dim,) float32 array."""
        text = f"{self.query_prefix}{query}"
        key = _key("query", text)
        with _cache_lock:
            cached = _embedding_cache.get(key)
        if cached is not None:
            return cached
        vec = np.asarray(next(iter(self.model.query_embed(text))), dtype=np.float32)
        with _cache_lock:
            _embedding_cache[key] = vec
        return vec

    # Backwards-compatible names used by earlier versions.
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        return self.embed_passages(texts)

    def embed_text(self, text: str) -> np.ndarray:
        return self.embed_passages([text])[0]
