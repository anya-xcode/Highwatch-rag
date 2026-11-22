"""
Document Registry
A small JSON database (DOCUMENTS_DB_PATH) tracking every document:
processing status, content hash (duplicate detection), stored original
(for re-indexing), and citation metadata such as the Google Drive link.
"""

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from persistence.backends import PersistenceBackend, get_persistence
from persistence.files import atomic_write_json, quarantine, read_json

logger = structlog.get_logger(__name__)

STATUS_PROCESSING = "processing"
STATUS_INDEXED = "indexed"
STATUS_FAILED = "failed"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DocumentRegistry:
    """Thread-safe, crash-safe registry of documents keyed by doc_id."""

    def __init__(self, path: str | Path, persistence: Optional[PersistenceBackend] = None):
        self.path = Path(path)
        self._persistence = persistence or get_persistence()
        self._lock = threading.RLock()
        self._docs: dict[str, dict] = {}
        self.load_error: Optional[str] = None
        self._load()

    # ── Queries ────────────────────────────────────────────

    def get(self, doc_id: str) -> Optional[dict]:
        with self._lock:
            doc = self._docs.get(doc_id)
            return dict(doc) if doc else None

    def all(self) -> list[dict]:
        with self._lock:
            return [dict(d) for d in self._docs.values()]

    def find_by_hash(self, content_hash: str) -> Optional[dict]:
        """Return an indexed/processing document with identical content, if any."""
        with self._lock:
            for doc in self._docs.values():
                if doc.get("content_hash") == content_hash and doc.get("status") in (
                    STATUS_INDEXED,
                    STATUS_PROCESSING,
                ):
                    return dict(doc)
        return None

    def __len__(self) -> int:
        with self._lock:
            return len(self._docs)

    # ── Mutations ──────────────────────────────────────────

    def upsert(self, record: dict) -> dict:
        with self._lock:
            now = utc_now()
            existing = self._docs.get(record["doc_id"], {})
            merged = {**existing, **record}
            merged.setdefault("created_at", now)
            merged["updated_at"] = now
            self._docs[record["doc_id"]] = merged
            self._write()
            return dict(merged)

    def update(self, doc_id: str, **fields) -> Optional[dict]:
        with self._lock:
            if doc_id not in self._docs:
                return None
            self._docs[doc_id].update(fields)
            self._docs[doc_id]["updated_at"] = utc_now()
            self._write()
            return dict(self._docs[doc_id])

    def delete(self, doc_id: str) -> Optional[dict]:
        with self._lock:
            doc = self._docs.pop(doc_id, None)
            if doc is not None:
                self._write()
            return doc

    def clear(self) -> None:
        with self._lock:
            self._docs = {}
            self._write()

    def backfill_from_index(self, chunk_metadata: list[dict], storage_dir: str | Path) -> int:
        """
        Register documents that exist in a pre-2.0 FAISS index but not in the
        registry, so they appear in the UI and can be re-indexed.
        """
        storage = Path(storage_dir)
        counts: dict[str, dict] = {}
        for meta in chunk_metadata:
            doc_id = meta.get("doc_id")
            if not doc_id:
                continue
            entry = counts.setdefault(doc_id, {"file_name": meta.get("file_name", "Unknown"), "chunks": 0})
            entry["chunks"] += 1

        added = 0
        with self._lock:
            for doc_id, info in counts.items():
                if doc_id in self._docs:
                    continue
                stored = None
                source = "upload"
                for folder, src in (("uploads", "upload"), ("downloads", "gdrive")):
                    matches = sorted((storage / folder).glob(f"{doc_id}_*"))
                    if matches:
                        stored, source = str(matches[0]), src
                        break
                now = utc_now()
                self._docs[doc_id] = {
                    "doc_id": doc_id,
                    "file_name": info["file_name"],
                    "source": source,
                    "status": STATUS_INDEXED,
                    "chunk_count": info["chunks"],
                    "stored_path": stored,
                    "content_hash": None,
                    "legacy": True,
                    "created_at": now,
                    "updated_at": now,
                }
                added += 1
            if added:
                self._write()
                logger.info("Backfilled registry from existing index", documents=added)
        return added

    # ── Persistence ────────────────────────────────────────

    def _load(self) -> None:
        try:
            data = read_json(self.path, default={})
            docs = data.get("documents", data) if isinstance(data, dict) else {}
            if not isinstance(docs, dict):
                raise ValueError("unexpected registry format")
            self._docs = docs
        except Exception as e:  # noqa: BLE001
            moved = quarantine(self.path)
            self.load_error = f"Document registry was unreadable and was moved to {moved}: {e}"
            logger.error("Failed to load document registry", error=str(e), moved_to=str(moved))
            self._docs = {}

    def _write(self) -> None:
        atomic_write_json(self.path, {"version": 1, "documents": self._docs})
        self._persistence.persist(self.path)
