"""
API Request/Response Models
Pydantic models for API validation and serialization.

Fields from version 1 are kept unchanged so existing clients keep working;
new fields are additive.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Sync Drive ──────────────────────────────────────────────

class SyncRequest(BaseModel):
    """Request to sync documents from Google Drive."""
    folder_ids: Optional[list[str]] = Field(
        default=None,
        description="Optional list of Google Drive folder IDs to sync. Uses configured defaults if empty.",
    )


class SyncedFile(BaseModel):
    """Details of a synced file."""
    id: str
    name: str
    path: Optional[str] = None
    mime_type: Optional[str] = None


class SyncError(BaseModel):
    """Sync error details."""
    id: str
    name: str
    error: str


class SyncResponse(BaseModel):
    """Response after syncing Google Drive."""
    status: str = "success"
    message: str
    new_files: list[SyncedFile] = []
    updated_files: list[SyncedFile] = []
    unchanged_files: list[SyncedFile] = []
    removed_files: list[SyncedFile] = []
    errors: list[SyncError] = []
    total_chunks_created: int = 0
    timestamp: str = ""


# ── Ask / Query ─────────────────────────────────────────────

AnswerStatus = Literal["answered", "extractive", "insufficient_context", "no_documents", "llm_error"]


class AskRequest(BaseModel):
    """Request to ask a question against the knowledge base."""
    query: str = Field(
        ...,
        description="The question to ask.",
        min_length=3,
        max_length=2000,
        examples=["What are our company policies on compliance?"],
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Number of relevant chunks to retrieve.",
    )
    filter_source: Optional[str] = Field(
        default=None,
        description="Filter results to a specific source file name.",
    )


class SourceDocument(BaseModel):
    """A retrieved chunk that was given to the model as context."""
    file_name: str
    chunk_text: str
    score: float
    doc_id: str
    chunk_index: int
    page: Optional[int] = None


class Citation(BaseModel):
    """A source cited in the answer. `number` matches the [n] marker in the answer text."""
    number: int
    doc_id: str
    file_name: str
    chunk_index: int
    page: Optional[int] = None
    page_end: Optional[int] = None
    section: Optional[str] = None
    score: float
    snippet: str
    url: Optional[str] = None
    source: Optional[str] = None


class AskResponse(BaseModel):
    """Response containing the AI-generated answer."""
    answer: str
    sources: list[str] = Field(description="Unique source file names used.")
    source_details: list[SourceDocument] = Field(description="Retrieved chunks with scores (numbered [1]..[n]).")
    query: str
    chunks_retrieved: int
    answer_status: AnswerStatus = "answered"
    citations: list[Citation] = []
    provider: Optional[str] = None
    model: Optional[str] = None
    warning: Optional[str] = None


# ── Status / Health ─────────────────────────────────────────

class HealthResponse(BaseModel):
    """Liveness check response."""
    status: str = "healthy"
    version: str
    index_stats: Optional[dict] = None


class ReadinessResponse(BaseModel):
    """Readiness check: is the app able to serve requests?"""
    status: Literal["ready", "degraded", "not_ready"]
    version: str
    checks: dict[str, dict]


class PublicConfig(BaseModel):
    """Non-secret configuration the UI needs."""
    version: str
    llm_provider: str
    llm_model: Optional[str] = None
    embedding_model: str
    max_upload_mb: int
    allowed_extensions: list[str]
    auth_required: bool
    drive_configured: bool
    storage_backend: str


class DocumentListItem(BaseModel):
    """A document in the knowledge base."""
    doc_id: str
    file_name: str
    chunk_count: int
    source: str
    status: str = "indexed"
    page_count: Optional[int] = None
    size_bytes: Optional[int] = None
    error: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DocumentsResponse(BaseModel):
    """List of documents in the knowledge base."""
    documents: list[DocumentListItem]
    total_documents: int
    total_chunks: int


# ── Upload ──────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Response after uploading and processing a document."""
    status: str = "success"
    message: str
    doc_id: str
    file_name: str
    chunks_created: int
    document: Optional[DocumentListItem] = None


class ReindexResponse(BaseModel):
    status: str
    message: str
    reindexed: list[dict]
    failed: list[dict]
