"""
Highwatch RAG - Main Application
Personal ChatGPT over Google Drive and uploaded documents.
"""

import os
import threading
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from api.dependencies import get_services
from api.routes import router
from config.logging import configure_logging
from config.settings import APP_VERSION, get_settings
from persistence.backends import get_persistence

logger = structlog.get_logger(__name__)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
QUIET_PATHS = ("/health", "/api/v1/health", "/static/")


def _startup_sync() -> None:
    """Optional Drive sync on startup (useful on hosts with ephemeral disks)."""
    from processing.pipeline import run_drive_sync

    services = get_services()
    if not services.sync_lock.acquire(blocking=False):
        return
    try:
        result = run_drive_sync(services.gdrive, services.pipeline)
        logger.info(
            "Startup Drive sync finished",
            new=len(result["new_files"]),
            updated=len(result["updated_files"]),
            errors=len(result["errors"]),
        )
    except Exception as e:  # noqa: BLE001
        logger.error("Startup Drive sync failed", error=str(e))
    finally:
        services.sync_lock.release()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: restore storage, load the index, register legacy documents."""
    settings = get_settings()
    settings.ensure_storage_dirs()

    persistence = get_persistence()
    if persistence.name != "local":
        restored = await run_in_threadpool(persistence.restore)
        logger.info("Storage restored", backend=persistence.name, files=restored)

    services = get_services()
    services.registry.backfill_from_index(services.store.metadata, settings.storage_dir)

    llm_ok, llm_problem = services.llm.check_configuration()
    logger.info(
        "Highwatch RAG starting",
        version=APP_VERSION,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        embedding_model=settings.embedding_model,
        storage_backend=settings.storage_backend,
        documents=len(services.registry),
        vectors=services.store.total_vectors,
        auth_required=bool(settings.api_key),
    )
    if not llm_ok:
        logger.warning("LLM provider is not configured; answers will fall back to excerpts", problem=llm_problem)

    if settings.auto_sync_on_startup and services.gdrive.is_configured():
        threading.Thread(target=_startup_sync, name="startup-drive-sync", daemon=True).start()

    yield
    logger.info("Highwatch RAG shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    app = FastAPI(
        title="Highwatch RAG",
        description=(
            "🔍 **Intelligent Document Q&A System**\n\n"
            "A RAG (Retrieval-Augmented Generation) system that connects to Google Drive, "
            "processes documents, and answers questions with cited sources.\n\n"
            "### Quick Start\n"
            "1. `POST /api/v1/upload` or `POST /api/v1/sync-drive` — add documents\n"
            "2. `POST /api/v1/ask` — ask questions about them\n\n"
            "### Architecture\n"
            "Google Drive / Upload → Parser → Chunker → FastEmbed → FAISS → LLM → Answer + citations"
        ),
        version=APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        """Request IDs, Cloud Logging trace correlation, access logs, upload size guard."""
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        trace = request.headers.get("x-cloud-trace-context")
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if trace and project:
            structlog.contextvars.bind_contextvars(
                **{"logging.googleapis.com/trace": f"projects/{project}/traces/{trace.split('/')[0]}"}
            )

        # Reject oversized uploads before the body is read.
        if request.method == "POST" and request.url.path.rstrip("/").endswith("/upload"):
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > settings.max_upload_bytes + 1_048_576:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"File is too large. Maximum is {settings.max_upload_mb} MB."},
                )

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            # Revalidate the UI on every load (ETag makes this a cheap 304), so a
            # browser never keeps running an old index.html, style.css or app.js.
            response.headers.setdefault("Cache-Control", "no-cache")
        log = logger.debug if request.url.path.startswith(QUIET_PATHS) else logger.info
        log(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    # CORS is only needed when another origin calls the API; the bundled UI is
    # same-origin. Never combine "*" with credentials.
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type", "X-API-Key"],
        )

    # Trust X-Forwarded-* from the platform proxy (Render, Cloud Run) for HTTPS URLs.
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    app.include_router(router, prefix="/api/v1")
    # Same routes at the root for backwards compatibility (hidden from the docs).
    app.include_router(router, include_in_schema=False)

    @app.get("/", include_in_schema=False)
    async def read_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=os.environ.get("RELOAD", "false").lower() == "true",
        log_level=settings.log_level,
    )
