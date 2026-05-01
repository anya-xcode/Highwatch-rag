"""
Highwatch RAG - Main Application
Personal ChatGPT over Google Drive
"""

import os
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from api.routes import router
from config.settings import get_settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    settings = get_settings()
    logger.info(
        "Highwatch RAG starting",
        host=settings.host,
        port=settings.port,
        llm_provider=settings.llm_provider,
        embedding_model=settings.embedding_model,
    )
    settings.ensure_storage_dirs()
    yield
    logger.info("Highwatch RAG shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Highwatch RAG",
        description=(
            "🔍 **Intelligent Document Q&A System**\n\n"
            "A RAG (Retrieval-Augmented Generation) system that connects to Google Drive, "
            "processes documents, and answers questions using AI.\n\n"
            "### Quick Start\n"
            "1. `POST /sync-drive` — Sync your Google Drive documents\n"
            "2. `POST /ask` — Ask questions about your documents\n"
            "3. `POST /upload` — Upload documents directly\n\n"
            "### Architecture\n"
            "Google Drive → Parser → Chunker → Embeddings → FAISS → LLM → Answer"
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trust proxy headers for HTTPS on Render
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    # Register API routes
    app.include_router(router, prefix="/api/v1")
    
    # Also register routes at root level for convenience
    app.include_router(router)

    # Mount Static Files (Frontend)
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    os.makedirs(frontend_dir, exist_ok=True)
    
    # Root route for frontend
    @app.get("/")
    async def read_index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    # Mount the rest of the frontend assets
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level,
    )
