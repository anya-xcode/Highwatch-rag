"""
Embedding Service
Generates vector embeddings for text using SentenceTransformers.
Supports batch processing and caching for efficiency.
"""

from typing import Optional

import numpy as np
import structlog
from cachetools import LRUCache

from config.settings import get_settings

logger = structlog.get_logger(__name__)

# Global cache for embeddings (keyed by text hash)
_embedding_cache: LRUCache = LRUCache(maxsize=10000)


class EmbeddingService:
    """Generates embeddings using SentenceTransformers models."""

    def __init__(self, model_name: Optional[str] = None):
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.batch_size = settings.embedding_batch_size
        self.dimension = settings.embedding_dimension
        self._model = None

    @property
    def model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            logger.info("Loading embedding model", model=self.model_name)
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            # Update dimension based on actual model
            self.dimension = self._model.get_sentence_embedding_dimension()
            logger.info(
                "Embedding model loaded",
                model=self.model_name,
                dimension=self.dimension,
            )
        return self._model

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text string.
        
        Args:
            text: Input text to embed.
            
        Returns:
            Embedding vector as numpy array.
        """
        # Check cache
        cache_key = hash(text)
        if cache_key in _embedding_cache:
            return _embedding_cache[cache_key]

        embedding = self.model.encode(
            text,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        embedding = np.array(embedding, dtype=np.float32)

        # Cache the result
        _embedding_cache[cache_key] = embedding
        return embedding

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """
        Generate embeddings for a batch of texts efficiently.
        
        Args:
            texts: List of text strings to embed.
            
        Returns:
            2D numpy array of embeddings (n_texts x dimension).
        """
        if not texts:
            return np.array([], dtype=np.float32).reshape(0, self.dimension)

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
            
            new_embeddings = self.model.encode(
                uncached_texts,
                batch_size=self.batch_size,
                show_progress_bar=len(uncached_texts) > 100,
                normalize_embeddings=True,
            )
            new_embeddings = np.array(new_embeddings, dtype=np.float32)

            # Cache new embeddings
            for idx, text, emb in zip(uncached_indices, uncached_texts, new_embeddings):
                cache_key = hash(text)
                _embedding_cache[cache_key] = emb
                cached_results[idx] = emb

        # Assemble in order
        all_embeddings = np.array(
            [cached_results[i] for i in range(len(texts))], dtype=np.float32
        )

        return all_embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate embedding for a search query.
        Uses the same model but could apply query-specific preprocessing.
        
        Args:
            query: Search query text.
            
        Returns:
            Query embedding vector.
        """
        # Optionally add query prefix for asymmetric models
        return self.embed_text(query)
