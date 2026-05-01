"""
Embedding Service
Generates vector embeddings for text using FastEmbed (Memory Efficient).
Supports batch processing and caching for efficiency.
"""

from typing import Optional, List
import numpy as np
import structlog
from cachetools import LRUCache
from fastembed import TextEmbedding

from config.settings import get_settings

logger = structlog.get_logger(__name__)

# Global cache for embeddings (keyed by text hash)
_embedding_cache: LRUCache = LRUCache(maxsize=10000)


class EmbeddingService:
    """Generates embeddings using FastEmbed models."""

    def __init__(self, model_name: Optional[str] = None):
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.batch_size = settings.embedding_batch_size
        self._model = None

    @property
    def model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            logger.info("Loading embedding model", model=self.model_name)
            # TextEmbedding is much lighter than SentenceTransformer/Torch
            self._model = TextEmbedding(model_name=self.model_name)
            logger.info(
                "Embedding model loaded",
                model=self.model_name,
            )
        return self._model

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text string.
        """
        cache_key = hash(text)
        if cache_key in _embedding_cache:
            return _embedding_cache[cache_key]

        # FastEmbed returns a generator
        embeddings = list(self.model.embed([text]))
        embedding = np.array(embeddings[0], dtype=np.float32)

        _embedding_cache[cache_key] = embedding
        return embedding

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a batch of texts efficiently.
        """
        if not texts:
            return np.array([], dtype=np.float32)

        # Split into cached and uncached
        cached_results = {}
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            cache_key = hash(text)
            if cache_key in _embedding_cache:
                cached_results[i] = _embedding_cache[cache_key]
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        # Batch encode uncached texts
        if uncached_texts:
            logger.info(
                "Batch embedding",
                total=len(texts),
                cached=len(cached_results),
                to_encode=len(uncached_texts),
            )
            
            # FastEmbed.embed returns a generator of numpy arrays
            new_embeddings_gen = self.model.embed(uncached_texts, batch_size=self.batch_size)
            new_embeddings = list(new_embeddings_gen)

            # Cache new embeddings
            for idx, text, emb in zip(uncached_indices, uncached_texts, new_embeddings):
                cache_key = hash(text)
                emb_np = np.array(emb, dtype=np.float32)
                _embedding_cache[cache_key] = emb_np
                cached_results[idx] = emb_np

        # Assemble in order
        all_embeddings = np.array(
            [cached_results[i] for i in range(len(texts))], dtype=np.float32
        )

        return all_embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate embedding for a search query.
        """
        return self.embed_text(query)
