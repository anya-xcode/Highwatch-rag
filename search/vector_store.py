"""
Vector Store
FAISS-based vector storage and retrieval for document chunks.

Files (FAISS_INDEX_PATH = ./storage/faiss_index by default):
- faiss_index.bin            FAISS IndexFlatIP (exact cosine search)
- faiss_index_metadata.json  chunk metadata, one entry per vector
- faiss_index_manifest.json  embedding model, dimension and vector count

Writes are atomic. On load, the files are checked against each other and
against the configured embedding model; anything inconsistent is moved aside
(never deleted) and the store starts empty, ready for POST /reindex.
"""

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
import structlog

from config.settings import get_settings
from persistence.backends import PersistenceBackend, get_persistence
from persistence.files import atomic_write, atomic_write_json, quarantine, read_json

logger = structlog.get_logger(__name__)

INDEX_FORMAT_VERSION = 2


class VectorStoreError(RuntimeError):
    """Raised when the vector store cannot complete an operation."""


class VectorStore:
    """FAISS vector store for chunk embeddings with metadata."""

    def __init__(
        self,
        dimension: Optional[int] = None,
        index_path: Optional[str] = None,
        embedding_model: Optional[str] = None,
        persistence: Optional[PersistenceBackend] = None,
    ):
        settings = get_settings()
        self.dimension = dimension or settings.embedding_dimension
        self.index_path = index_path or settings.faiss_index_path
        self.index_file = f"{self.index_path}.bin"
        self.metadata_path = f"{self.index_path}_metadata.json"
        self.manifest_path = f"{self.index_path}_manifest.json"
        self.embedding_model = embedding_model or settings.embedding_model
        self.top_k = settings.top_k_results
        self.similarity_threshold = settings.similarity_threshold
        self._persistence = persistence or get_persistence()
        self._lock = threading.RLock()

        # Inner product on L2-normalized vectors == cosine similarity.
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata: list[dict] = []
        self.load_error: Optional[str] = None

        self._load()

    # ── Write operations ───────────────────────────────────

    def add(self, embeddings: np.ndarray, chunks_metadata: list[dict]) -> int:
        """Add embeddings and their metadata. Returns number of vectors added."""
        with self._lock:
            added = self._add_unlocked(embeddings, chunks_metadata)
            if added:
                self._save()
            return added

    def replace_document(self, doc_id: str, embeddings: np.ndarray, chunks_metadata: list[dict]) -> int:
        """Atomically replace all vectors of a document (one save)."""
        with self._lock:
            self._remove_unlocked(doc_id)
            added = self._add_unlocked(embeddings, chunks_metadata)
            self._save()
            return added

    def delete_by_doc_id(self, doc_id: str) -> int:
        """Delete all vectors of a document. Returns number of vectors removed."""
        with self._lock:
            removed = self._remove_unlocked(doc_id)
            if removed:
                self._save()
                logger.info("Deleted vectors", doc_id=doc_id, removed=removed)
            return removed

    def clear(self) -> None:
        """Clear all data from the store."""
        with self._lock:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []
            self.load_error = None
            self._save()
            logger.info("Vector store cleared")

    # ── Read operations ────────────────────────────────────

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: Optional[int] = None,
        filter_metadata: Optional[dict] = None,
        min_score: Optional[float] = None,
    ) -> list[dict]:
        """
        Return up to top_k chunks most similar to the query, best first.

        Each result is the chunk metadata plus a "score" (cosine similarity).
        Results scoring below `min_score` (default SIMILARITY_THRESHOLD) are
        dropped.
        """
        with self._lock:
            if self.index.ntotal == 0:
                return []

            k = top_k or self.top_k
            threshold = self.similarity_threshold if min_score is None else min_score
            query = self._prepare(query_embedding)

            # Flat index: when filtering, scan everything so matches aren't missed.
            search_k = self.index.ntotal if filter_metadata else min(k, self.index.ntotal)
            scores, indices = self.index.search(query, search_k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1 or score < threshold:
                    continue
                meta = self.metadata[idx]
                if filter_metadata and not all(meta.get(key) == value for key, value in filter_metadata.items()):
                    continue
                result = dict(meta)
                result["score"] = float(score)
                results.append(result)
                if len(results) >= k:
                    break

        logger.info("Search completed", results=len(results), top_score=results[0]["score"] if results else None)
        return results

    def doc_ids(self) -> set[str]:
        with self._lock:
            return {m.get("doc_id", "") for m in self.metadata}

    def chunk_counts(self) -> dict[str, int]:
        with self._lock:
            counts: dict[str, int] = {}
            for m in self.metadata:
                doc_id = m.get("doc_id", "")
                counts[doc_id] = counts.get(doc_id, 0) + 1
            return counts

    @property
    def total_vectors(self) -> int:
        return int(self.index.ntotal)

    def get_stats(self) -> dict:
        """Index statistics (safe to expose: no document contents or IDs)."""
        with self._lock:
            return {
                "total_vectors": int(self.index.ntotal),
                "dimension": self.dimension,
                "unique_documents": len({m.get("doc_id", "") for m in self.metadata}),
                "embedding_model": self.embedding_model,
                "load_error": self.load_error,
            }

    # ── Internals ──────────────────────────────────────────

    def _prepare(self, vectors: np.ndarray) -> np.ndarray:
        arr = np.array(vectors, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] != self.dimension:
            raise VectorStoreError(
                f"Embedding dimension {arr.shape[1]} does not match the index dimension "
                f"{self.dimension}. Did EMBEDDING_MODEL change? Run POST /reindex."
            )
        arr = np.ascontiguousarray(arr)
        faiss.normalize_L2(arr)
        return arr

    def _add_unlocked(self, embeddings: np.ndarray, chunks_metadata: list[dict]) -> int:
        if len(embeddings) == 0:
            return 0
        if len(embeddings) != len(chunks_metadata):
            raise ValueError(
                f"Embeddings count ({len(embeddings)}) != metadata count ({len(chunks_metadata)})"
            )
        vectors = self._prepare(embeddings)
        self.index.add(vectors)
        self.metadata.extend(chunks_metadata)
        logger.info("Added vectors to store", count=len(vectors), total=self.index.ntotal)
        return len(vectors)

    def _remove_unlocked(self, doc_id: str) -> int:
        keep = [i for i, m in enumerate(self.metadata) if m.get("doc_id") != doc_id]
        removed = len(self.metadata) - len(keep)
        if removed == 0:
            return 0
        new_index = faiss.IndexFlatIP(self.dimension)
        if keep:
            all_vectors = self.index.reconstruct_n(0, self.index.ntotal)
            new_index.add(np.ascontiguousarray(all_vectors[keep]))
        self.index = new_index
        self.metadata = [self.metadata[i] for i in keep]
        return removed

    def _save(self) -> None:
        """Persist index, metadata and manifest atomically. Raises on failure."""
        try:
            Path(self.index_file).parent.mkdir(parents=True, exist_ok=True)
            atomic_write(self.index_file, lambda tmp: faiss.write_index(self.index, tmp))
            atomic_write_json(self.metadata_path, self.metadata)
            atomic_write_json(
                self.manifest_path,
                {
                    "version": INDEX_FORMAT_VERSION,
                    "embedding_model": self.embedding_model,
                    "dimension": self.dimension,
                    "vectors": int(self.index.ntotal),
                    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
            )
        except Exception as e:
            logger.error("Failed to save vector store", error=str(e))
            raise VectorStoreError(f"Failed to save the vector index: {e}") from e
        self._persistence.persist(self.index_file, self.metadata_path, self.manifest_path)
        logger.debug("Saved vector store", vectors=self.index.ntotal)

    def _load(self) -> None:
        """Load index + metadata from disk, quarantining anything inconsistent."""
        index_exists = Path(self.index_file).exists()
        meta_exists = Path(self.metadata_path).exists()
        if not index_exists and not meta_exists:
            return

        problem = None
        try:
            if not (index_exists and meta_exists):
                raise VectorStoreError("index and metadata files are not both present")
            index = faiss.read_index(self.index_file)
            metadata = read_json(self.metadata_path, default=[])
            if not isinstance(metadata, list):
                raise VectorStoreError("metadata file has an unexpected format")
            if index.ntotal != len(metadata):
                raise VectorStoreError(
                    f"index has {index.ntotal} vectors but metadata has {len(metadata)} entries"
                )
            manifest = read_json(self.manifest_path, default={}) or {}
            stored_model = manifest.get("embedding_model")
            if stored_model and stored_model != self.embedding_model:
                problem = (
                    f"index was built with '{stored_model}' but EMBEDDING_MODEL is "
                    f"'{self.embedding_model}'"
                )
            elif index.d != self.dimension:
                problem = f"index dimension {index.d} != EMBEDDING_DIMENSION {self.dimension}"
        except Exception as e:  # noqa: BLE001
            problem = str(e)

        if problem:
            moved = [str(p) for p in (
                quarantine(self.index_file, "stale"),
                quarantine(self.metadata_path, "stale"),
                quarantine(self.manifest_path, "stale"),
            ) if p]
            self.load_error = (
                f"Existing index could not be used ({problem}). It was moved aside and the store "
                "started empty. Run POST /reindex to rebuild it from the stored documents."
            )
            logger.error("Vector store not loaded", problem=problem, moved=moved)
            return

        self.index = index
        self.metadata = metadata
        logger.info("Loaded vector store", vectors=self.index.ntotal)
