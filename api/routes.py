"""
API Routes
FastAPI endpoints for the Highwatch RAG system.
"""

import uuid
from pathlib import Path
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from api.dependencies import get_services, require_api_key
from api.models import (
    AskRequest,
    AskResponse,
    Citation,
    DocumentListItem,
    DocumentsResponse,
    HealthResponse,
    PublicConfig,
    ReadinessResponse,
    ReindexResponse,
    SourceDocument,
    SyncRequest,
    SyncResponse,
    UploadResponse,
)
from config.settings import APP_VERSION, get_settings
from connectors.gdrive import DriveAuthError
from persistence.files import atomic_write_bytes
from processing.pipeline import run_drive_sync, sha256_bytes
from processing.validation import (
    DocumentParseError,
    DocumentValidationError,
    sanitize_filename,
    validate_document,
)
from search.vector_store import VectorStoreError

logger = structlog.get_logger(__name__)
router = APIRouter()
protected = [Depends(require_api_key)]

NO_DOCUMENTS_MESSAGE = "No documents are indexed yet. Upload a file or sync Google Drive first."
INSUFFICIENT_CONTEXT_MESSAGE = (
    "I couldn't find the answer to that in your indexed documents. "
    "Try rephrasing the question, or add a document that covers it."
)


# ── Helpers ─────────────────────────────────────────────────

def _snippet(text: str, limit: int = 300) -> str:
    text = text or ""
    return text[:limit] + "..." if len(text) > limit else text


def _citation(number: int, chunk: dict) -> Citation:
    return Citation(
        number=number,
        doc_id=chunk.get("doc_id", ""),
        file_name=chunk.get("file_name", "Unknown"),
        chunk_index=chunk.get("chunk_index", 0),
        page=chunk.get("page"),
        page_end=chunk.get("page_end"),
        section=chunk.get("section"),
        score=round(float(chunk.get("score", 0.0)), 4),
        snippet=_snippet(chunk.get("text", "")),
        url=(chunk.get("metadata") or {}).get("url"),
        source=chunk.get("source"),
    )


def _unique(names) -> list[str]:
    return list(dict.fromkeys(names))


def _doc_item(record: dict, chunk_count: Optional[int] = None) -> DocumentListItem:
    return DocumentListItem(
        doc_id=record["doc_id"],
        file_name=record.get("file_name", "Unknown"),
        chunk_count=chunk_count if chunk_count is not None else int(record.get("chunk_count") or 0),
        source=record.get("source", "unknown"),
        status=record.get("status", "indexed"),
        page_count=record.get("page_count"),
        size_bytes=record.get("size_bytes"),
        error=record.get("error"),
        url=record.get("url"),
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Read an upload, refusing to buffer more than max_bytes."""
    buf = bytearray()
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File is too large. Maximum is {max_bytes // 1_048_576} MB.",
            )
    return bytes(buf)


# ── System ──────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Liveness check: the process is up and the index is loaded."""
    services = get_services()
    return HealthResponse(status="healthy", version=APP_VERSION, index_stats=services.store.get_stats())


@router.get("/health/ready", response_model=ReadinessResponse, tags=["System"])
async def readiness_check(response: Response):
    """Readiness check: storage, index, registry and LLM configuration.

    Returns 503 only when storage is unusable; missing optional pieces
    (e.g. no LLM key) report "degraded" with HTTP 200.
    """
    settings = get_settings()
    services = get_services()
    checks: dict[str, dict] = {}

    try:
        probe = Path(settings.storage_dir) / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks["storage"] = {"ok": True, **services.persistence.describe()}
    except Exception as e:  # noqa: BLE001
        checks["storage"] = {"ok": False, "error": str(e)}

    checks["vector_store"] = {
        "ok": services.store.load_error is None,
        "vectors": services.store.total_vectors,
        "error": services.store.load_error,
    }
    checks["registry"] = {
        "ok": services.registry.load_error is None,
        "documents": len(services.registry),
        "error": services.registry.load_error,
    }
    llm_ok, llm_problem = services.llm.check_configuration()
    checks["llm"] = {"ok": llm_ok, "provider": services.llm.provider, "model": services.llm.model, "error": llm_problem}
    checks["embedding_model"] = {
        "ok": True,
        "model": services.embedder.model_name,
        "loaded": services.embedder.is_loaded,
    }
    checks["google_drive"] = {"ok": True, "configured": services.gdrive.is_configured()}

    if not checks["storage"]["ok"]:
        overall = "not_ready"
        response.status_code = 503
    elif all(c.get("ok") for c in checks.values()):
        overall = "ready"
    else:
        overall = "degraded"
    return ReadinessResponse(status=overall, version=APP_VERSION, checks=checks)


@router.get("/config", response_model=PublicConfig, tags=["System"])
async def public_config():
    """Non-secret settings used by the web UI."""
    settings = get_settings()
    services = get_services()
    return PublicConfig(
        version=APP_VERSION,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        embedding_model=settings.embedding_model,
        max_upload_mb=settings.max_upload_mb,
        allowed_extensions=sorted(settings.allowed_extension_set),
        auth_required=bool(settings.api_key),
        drive_configured=services.gdrive.is_configured(),
        storage_backend=settings.storage_backend,
    )


# ── Google Drive ────────────────────────────────────────────

@router.post("/sync-drive", response_model=SyncResponse, tags=["Google Drive"], dependencies=protected)
async def sync_drive(request: Optional[SyncRequest] = None):
    """
    Sync documents from Google Drive.

    Downloads new/changed files, indexes them, and removes files that were
    deleted from Drive. Files that fail are retried on the next sync.
    """
    services = get_services()
    folder_ids = request.folder_ids if request else None

    if not services.sync_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A Google Drive sync is already running.")
    try:
        result = await run_in_threadpool(run_drive_sync, services.gdrive, services.pipeline, folder_ids)
    except (FileNotFoundError, DriveAuthError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error("Sync failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")
    finally:
        services.sync_lock.release()

    processed = len(result["new_files"]) + len(result["updated_files"])
    message = (
        f"Sync completed. Indexed {processed} new/changed file(s) "
        f"({result['total_chunks_created']} chunks), removed {len(result['removed_files'])}, "
        f"unchanged {len(result['unchanged_files'])}."
    )
    if result["errors"]:
        message += f" {len(result['errors'])} file(s) failed and will be retried next sync."
    return SyncResponse(
        status="success" if not result["errors"] else "partial",
        message=message,
        **result,
    )


# ── Ask ─────────────────────────────────────────────────────

@router.post("/ask", response_model=AskResponse, tags=["RAG Query"], dependencies=protected)
async def ask_question(request: AskRequest):
    """
    Ask a question against the document knowledge base.

    Retrieves the most relevant chunks, asks the configured LLM to answer from
    them only, and returns the answer with numbered citations. If the documents
    don't contain the answer, `answer_status` is "insufficient_context".
    """
    services = get_services()
    base = {"query": request.query, "provider": services.llm.provider, "model": services.llm.model}

    if services.store.total_vectors == 0:
        return AskResponse(
            answer=NO_DOCUMENTS_MESSAGE,
            sources=[],
            source_details=[],
            chunks_retrieved=0,
            answer_status="no_documents",
            **base,
        )

    try:
        query_embedding = await run_in_threadpool(services.embedder.embed_query, request.query)
        filter_meta = {"file_name": request.filter_source} if request.filter_source else None
        results = await run_in_threadpool(services.store.search, query_embedding, request.top_k, filter_meta)
    except VectorStoreError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error("Retrieval failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process question: {e}")

    if not results:
        return AskResponse(
            answer=INSUFFICIENT_CONTEXT_MESSAGE,
            sources=[],
            source_details=[],
            chunks_retrieved=0,
            answer_status="insufficient_context",
            **base,
        )

    source_details = [
        SourceDocument(
            file_name=r.get("file_name", "Unknown"),
            chunk_text=_snippet(r.get("text", "")),
            score=float(r.get("score", 0.0)),
            doc_id=r.get("doc_id", ""),
            chunk_index=r.get("chunk_index", 0),
            page=r.get("page"),
        )
        for r in results
    ]
    common = {"source_details": source_details, "chunks_retrieved": len(results), **base}

    llm_answer = await services.llm.generate_answer(request.query, results)

    if llm_answer.status == "insufficient_context":
        return AskResponse(answer=INSUFFICIENT_CONTEXT_MESSAGE, sources=[], answer_status="insufficient_context", **common)

    warning = None
    status = llm_answer.status
    if status == "llm_error":
        fallback = services.llm.extractive_answer(results)
        warning = (
            f"The AI model ({services.llm.provider}) failed: {llm_answer.error}. "
            "Showing the most relevant passages instead."
        )
        text, cited = fallback.text, fallback.cited
    else:
        text, cited = llm_answer.text, llm_answer.cited
        if status == "answered" and not cited:
            warning = "The answer has no citations. Check it against the retrieved passages."

    citations = [_citation(n, results[n - 1]) for n in cited]
    used = citations if citations else [_citation(i, r) for i, r in enumerate(results, 1)]
    return AskResponse(
        answer=text,
        sources=_unique(c.file_name for c in used),
        answer_status=status,
        citations=citations,
        warning=warning,
        **common,
    )


# ── Documents ───────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, tags=["Documents"], dependencies=protected)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and index a document (PDF, DOCX, TXT or MD).

    Errors: 400 invalid file, 409 duplicate content, 413 too large,
    422 no extractable text.
    """
    settings = get_settings()
    services = get_services()

    file_name = sanitize_filename(file.filename)
    data = await _read_limited(file, settings.max_upload_bytes)
    try:
        validate_document(file_name, data, settings.allowed_extension_set, settings.max_upload_bytes)
    except DocumentValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    content_hash = sha256_bytes(data)

    def process():
        with services.pipeline.lock:
            duplicate = services.registry.find_by_hash(content_hash)
            if duplicate:
                return "duplicate", duplicate
            doc_id = str(uuid.uuid4())
            path = settings.uploads_dir / f"{doc_id}_{file_name}"
            atomic_write_bytes(path, data)
            try:
                record = services.pipeline.ingest(
                    doc_id=doc_id,
                    file_name=file_name,
                    file_path=path,
                    source="upload",
                    content_hash=content_hash,
                    size_bytes=len(data),
                )
            except Exception:
                path.unlink(missing_ok=True)
                services.registry.delete(doc_id)
                raise
            services.persistence.persist(path)
            return "ok", record

    try:
        outcome, record = await run_in_threadpool(process)
    except (DocumentParseError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error("Upload failed", file=file_name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    if outcome == "duplicate":
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"This file's content is already indexed as '{record['file_name']}'.",
                "doc_id": record["doc_id"],
                "file_name": record["file_name"],
            },
        )

    chunks = int(record.get("chunk_count") or 0)
    return UploadResponse(
        status="success",
        message=f"Document processed successfully. Created {chunks} chunks.",
        doc_id=record["doc_id"],
        file_name=record["file_name"],
        chunks_created=chunks,
        document=_doc_item(record),
    )


@router.get("/documents", response_model=DocumentsResponse, tags=["Documents"], dependencies=protected)
async def list_documents():
    """List all documents with their processing status."""
    services = get_services()
    counts = services.store.chunk_counts()
    records = services.registry.all()
    items = [
        _doc_item(r, counts.get(r["doc_id"]) if r.get("status") == "indexed" else None) for r in records
    ]
    items.sort(key=lambda d: d.created_at or "", reverse=True)
    return DocumentsResponse(
        documents=items,
        total_documents=len(items),
        total_chunks=services.store.total_vectors,
    )


@router.get("/documents/{doc_id}", response_model=DocumentListItem, tags=["Documents"], dependencies=protected)
async def get_document(doc_id: str):
    """Get one document's status and details."""
    record = get_services().registry.get(doc_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    return _doc_item(record)


@router.delete("/documents/{doc_id}", tags=["Documents"], dependencies=protected)
async def delete_document(doc_id: str):
    """Delete a document, its chunks and its stored file.

    For Google Drive documents the file is re-added on the next sync if it is
    still in Drive (Drive is the source of truth).
    """
    services = get_services()
    removed, record = await run_in_threadpool(services.pipeline.remove, doc_id)
    if removed == 0 and record is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    if record:
        if record.get("source") == "gdrive":
            services.gdrive.forget(doc_id)
        if record.get("stored_path"):
            services.persistence.remove(record["stored_path"])
    return {
        "status": "success",
        "message": f"Deleted {removed} chunks for document {doc_id}",
        "doc_id": doc_id,
        "chunks_removed": removed,
    }


@router.post("/reindex", response_model=ReindexResponse, tags=["System"], dependencies=protected)
async def reindex():
    """Rebuild the whole index from stored originals (recovery / model change)."""
    services = get_services()
    summary = await run_in_threadpool(services.pipeline.reindex_all)
    ok, failed = summary["reindexed"], summary["failed"]
    # Drive files whose original is gone are re-downloaded on the next sync.
    for item in failed:
        record = services.registry.get(item["doc_id"])
        if record and record.get("source") == "gdrive":
            services.gdrive.forget(item["doc_id"])
    return ReindexResponse(
        status="success" if not failed else "partial",
        message=f"Re-indexed {len(ok)} document(s); {len(failed)} failed.",
        reindexed=ok,
        failed=failed,
    )


@router.delete("/clear", tags=["System"], dependencies=protected)
async def clear_index():
    """Delete everything: index, document registry, Drive sync state and stored files."""
    settings = get_settings()
    services = get_services()
    if not services.sync_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A Google Drive sync is running; try again later.")
    try:
        def wipe() -> int:
            with services.pipeline.lock:
                services.store.clear()
                services.registry.clear()
                services.gdrive.reset_state()
                removed = 0
                for folder in (settings.uploads_dir, settings.downloads_dir):
                    for path in folder.glob("*"):
                        if path.is_file():
                            path.unlink(missing_ok=True)
                            services.persistence.remove(path)
                            removed += 1
                return removed

        files_removed = await run_in_threadpool(wipe)
    finally:
        services.sync_lock.release()
    return {"status": "success", "message": "Vector store cleared", "files_removed": files_removed}
