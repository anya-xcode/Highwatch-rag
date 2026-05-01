"""
Vector Store
FAISS-based vector storage and retrieval for document chunks.
Supports add, search, delete, and persistence.
"""

import json
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class VectorStore:
    """FAISS vector store for chunk embeddings with metadata."""

    def __init__(self, dimension: Optional[int] = None):
        settings = get_settings()
        self.dimension = dimension or settings.embedding_dimension
        self.index_path = settings.faiss_index_path
        self.metadata_path = f"{self.index_path}_metadata.json"
        self.top_k = settings.top_k_results
        self.similarity_threshold = settings.similarity_threshold

        # Initialize FAISS index (Inner Product for cosine similarity on normalized vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        
        # Metadata store: maps index position to chunk metadata
        self.metadata: list[dict] = []

        # Try to load existing index
        self._load()

    def add(self, embeddings: np.ndarray, chunks_metadata: list[dict]) -> int:
        """
        Add embeddings and their metadata to the store.
        
        Args:
            embeddings: 2D numpy array of embeddings.
            chunks_metadata: List of metadata dicts (one per embedding).
            
        Returns:
            Number of vectors added.
        """
        if len(embeddings) == 0:
            return 0

        if len(embeddings) != len(chunks_metadata):
            raise ValueError(
                f"Embeddings count ({len(embeddings)}) != metadata count ({len(chunks_metadata)})"
            )

        # Ensure correct shape and type
        embeddings = np.array(embeddings, dtype=np.float32)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)

        self.index.add(embeddings)
        self.metadata.extend(chunks_metadata)

        logger.info(
            "Added vectors to store",
            count=len(embeddings),
            total=self.index.ntotal,
        )

        # Auto-save after adding
        self._save()
        return len(embeddings)

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: Optional[int] = None,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        """
        Search for the most similar chunks to a query embedding.
        
        Args:
            query_embedding: Query vector.
            top_k: Number of results to return.
            filter_metadata: Optional metadata filters (key-value pairs to match).
            
        Returns:
            List of results with chunk metadata and similarity scores.
        """
        if self.index.ntotal == 0:
            logger.warning("Search on empty index")
            return []

        k = top_k or self.top_k

        # Prepare query vector
        query = np.array(query_embedding, dtype=np.float32)
        if query.ndim == 1:
            query = query.reshape(1, -1)
        faiss.normalize_L2(query)

        # Search with extra results for post-filtering
        search_k = k * 3 if filter_metadata else k
        search_k = min(search_k, self.index.ntotal)

        scores, indices = self.index.search(query, search_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for missing results
                continue

            if score < self.similarity_threshold:
                continue

            chunk_meta = self.metadata[idx].copy()

            # Apply metadata filters
            if filter_metadata:
                match = all(
                    chunk_meta.get(key) == value
                    for key, value in filter_metadata.items()
                )
                if not match:
                    continue

            chunk_meta["score"] = float(score)
            results.append(chunk_meta)

            if len(results) >= k:
                break

        logger.info("Search completed", results=len(results), top_score=results[0]["score"] if results else 0)
        return results

    def delete_by_doc_id(self, doc_id: str) -> int:
        """
        Delete all vectors associated with a document ID.
        Note: FAISS doesn't support deletion natively, so we rebuild the index.
        
        Args:
            doc_id: Document ID to remove.
            
        Returns:
            Number of vectors removed.
        """
        # Find indices to keep
        keep_indices = []
        removed = 0

        for i, meta in enumerate(self.metadata):
            if meta.get("doc_id") == doc_id:
                removed += 1
            else:
                keep_indices.append(i)

        if removed == 0:
            return 0

        # Rebuild index without deleted vectors
        if keep_indices:
            # Reconstruct vectors for remaining indices
            remaining_vectors = np.array(
                [self.index.reconstruct(i) for i in keep_indices], dtype=np.float32
            )
            remaining_metadata = [self.metadata[i] for i in keep_indices]

            # Reset and re-add
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []
            self.add(remaining_vectors, remaining_metadata)
        else:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []
            self._save()

        logger.info("Deleted vectors", doc_id=doc_id, removed=removed)
        return removed

    def get_stats(self) -> dict:
        """Get index statistics."""
        doc_ids = set(m.get("doc_id", "") for m in self.metadata)
        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "unique_documents": len(doc_ids),
            "documents": list(doc_ids),
        }

    def _save(self) -> None:
        """Persist the FAISS index and metadata to disk."""
        try:
            Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self.index, f"{self.index_path}.bin")
            
            with open(self.metadata_path, "w") as f:
                json.dump(self.metadata, f, indent=2, default=str)
            
            logger.debug("Saved vector store", vectors=self.index.ntotal)
        except Exception as e:
            logger.error("Failed to save vector store", error=str(e))

    def _load(self) -> None:
        """Load FAISS index and metadata from disk."""
        index_file = f"{self.index_path}.bin"
        
        if Path(index_file).exists() and Path(self.metadata_path).exists():
            try:
                self.index = faiss.read_index(index_file)
                with open(self.metadata_path, "r") as f:
                    self.metadata = json.load(f)
                
                # Update dimension from loaded index
                self.dimension = self.index.d
                
                logger.info(
                    "Loaded vector store",
                    vectors=self.index.ntotal,
                    metadata_entries=len(self.metadata),
                )
            except Exception as e:
                logger.error("Failed to load vector store, starting fresh", error=str(e))
                self.index = faiss.IndexFlatIP(self.dimension)
                self.metadata = []

    def clear(self) -> None:
        """Clear all data from the store."""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []
        self._save()
        logger.info("Vector store cleared")
