"""
Ingestion pipeline: parse → chunk → embed → store, with status tracking.

Processing runs inside the request (not as a background task) on purpose: on
Cloud Run with request-based billing, CPU is throttled after the response is
sent, so background work would stall. Status is still recorded per document
in the registry so the UI can show it.
"""

import hashlib
import threading
from pathlib import Path
from typing import Optional

import structlog

from processing.chunker import TextChunker
from processing.parser import DocumentParser
from processing.registry import (
    STATUS_FAILED,
    STATUS_INDEXED,
    STATUS_PROCESSING,
    DocumentRegistry,
)
from processing.validation import DocumentParseError

logger = structlog.get_logger(__name__)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class IngestionPipeline:
    """Indexes documents and keeps the registry in sync with the vector store."""

    def __init__(self, parser: DocumentParser, chunker: TextChunker, embedder, store, registry: DocumentRegistry):
        self.parser = parser
        self.chunker = chunker
        self.embedder = embedder
        self.store = store
        self.registry = registry
        # Serialize ingestion: keeps duplicate checks race-free and bounds memory.
        self.lock = threading.RLock()

    def index_file(
        self,
        *,
        file_path: str | Path,
        doc_id: str,
        file_name: str,
        source: str,
        url: Optional[str] = None,
    ) -> tuple[int, Optional[int]]:
        """Parse, chunk, embed and (re)place a document in the index.

        Returns (chunk_count, page_count). Raises DocumentParseError when no
        usable text can be extracted.
        """
        pages = self.parser.parse_pages(file_path)
        if not any(p.text.strip() for p in pages):
            raise DocumentParseError(
                "No extractable text found. Scanned or image-only PDFs need OCR, which is not supported."
            )
        page_count = len(pages) if any(p.number for p in pages) else None

        chunks = self.chunker.chunk_document(
            doc_id=doc_id,
            file_name=file_name,
            source=source,
            pages=pages,
            metadata={"url": url} if url else None,
        )
        embeddings = self.embedder.embed_passages([c.text for c in chunks])
        self.store.replace_document(doc_id, embeddings, [c.to_dict() for c in chunks])
        logger.info("Indexed document", doc_id=doc_id, file_name=file_name, chunks=len(chunks), source=source)
        return len(chunks), page_count

    def ingest(
        self,
        *,
        doc_id: str,
        file_name: str,
        file_path: str | Path,
        source: str,
        content_hash: Optional[str] = None,
        size_bytes: Optional[int] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """Index a stored file and record its status. Returns the registry record.

        On failure the record is marked "failed" with the error and the
        exception is re-raised.
        """
        with self.lock:
            record = {
                "doc_id": doc_id,
                "file_name": file_name,
                "source": source,
                "status": STATUS_PROCESSING,
                "stored_path": str(file_path),
                "content_hash": content_hash,
                "size_bytes": size_bytes,
                "error": None,
                **(extra or {}),
            }
            self.registry.upsert(record)
            try:
                chunk_count, page_count = self.index_file(
                    file_path=file_path,
                    doc_id=doc_id,
                    file_name=file_name,
                    source=source,
                    url=(extra or {}).get("url"),
                )
            except Exception as e:
                message = str(e) if isinstance(e, (DocumentParseError, ValueError)) else f"Processing failed: {e}"
                self.registry.update(doc_id, status=STATUS_FAILED, error=message)
                raise
            return self.registry.update(
                doc_id,
                status=STATUS_INDEXED,
                chunk_count=chunk_count,
                page_count=page_count,
                error=None,
            )

    def remove(self, doc_id: str, delete_file: bool = True) -> tuple[int, Optional[dict]]:
        """Remove a document's vectors, registry record and (optionally) stored file."""
        with self.lock:
            removed = self.store.delete_by_doc_id(doc_id)
            record = self.registry.delete(doc_id)
            if delete_file and record and record.get("stored_path"):
                Path(record["stored_path"]).unlink(missing_ok=True)
            return removed, record

    def reindex_all(self) -> dict:
        """Rebuild the whole index from stored originals."""
        with self.lock:
            self.store.clear()
            summary = {"reindexed": [], "failed": []}
            for record in self.registry.all():
                doc_id, name = record["doc_id"], record.get("file_name", "")
                stored = record.get("stored_path")
                if not stored or not Path(stored).exists():
                    msg = "Original file is missing; re-upload it or re-sync Google Drive."
                    self.registry.update(doc_id, status=STATUS_FAILED, error=msg, chunk_count=0)
                    summary["failed"].append({"doc_id": doc_id, "file_name": name, "error": msg})
                    continue
                try:
                    chunk_count, page_count = self.index_file(
                        file_path=stored,
                        doc_id=doc_id,
                        file_name=name,
                        source=record.get("source", "upload"),
                        url=record.get("url"),
                    )
                    self.registry.update(
                        doc_id, status=STATUS_INDEXED, chunk_count=chunk_count, page_count=page_count, error=None
                    )
                    summary["reindexed"].append({"doc_id": doc_id, "file_name": name, "chunks": chunk_count})
                except Exception as e:  # noqa: BLE001
                    self.registry.update(doc_id, status=STATUS_FAILED, error=str(e), chunk_count=0)
                    summary["failed"].append({"doc_id": doc_id, "file_name": name, "error": str(e)})
            logger.info("Reindex finished", ok=len(summary["reindexed"]), failed=len(summary["failed"]))
            return summary


def run_drive_sync(connector, pipeline: IngestionPipeline, folder_ids: Optional[list[str]] = None) -> dict:
    """Sync Google Drive into the index. State is committed per file only after
    it was indexed successfully, so failures are retried on the next sync."""
    plan = connector.plan_sync(folder_ids)
    total_chunks = 0
    new_files, updated_files = [], []

    for category, bucket in (("new_files", new_files), ("updated_files", updated_files)):
        for item in plan[category]:
            try:
                record = pipeline.ingest(
                    doc_id=item["id"],
                    file_name=item["name"],
                    file_path=item["path"],
                    source="gdrive",
                    content_hash=item["state"]["hash"],
                    size_bytes=item.get("size_bytes"),
                    extra={"url": item.get("url"), "drive_file_id": item["id"], "mime_type": item.get("mime_type")},
                )
                connector.commit(item["id"], item["state"])
                total_chunks += record.get("chunk_count", 0)
                bucket.append({k: item.get(k) for k in ("id", "name", "path", "mime_type")})
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to index Drive file", file=item["name"], error=str(e))
                plan["errors"].append({"id": item["id"], "name": item["name"], "error": str(e)})

    removed = []
    for item in plan["removed_files"]:
        pipeline.remove(item["id"], delete_file=True)
        connector.forget(item["id"])
        removed.append({"id": item["id"], "name": item["name"]})

    return {
        "new_files": new_files,
        "updated_files": updated_files,
        "unchanged_files": plan["unchanged_files"],
        "removed_files": removed,
        "errors": plan["errors"],
        "total_chunks_created": total_chunks,
        "timestamp": plan["timestamp"],
    }
