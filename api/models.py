"""
API Request/Response Models
Pydantic models for API validation and serialization.
"""

from typing import Optional

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
    errors: list[SyncError] = []
    total_chunks_created: int = 0
    timestamp: str = ""


# ── Ask / Query ─────────────────────────────────────────────

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
    """A source document used to generate the answer."""
    file_name: str
    chunk_text: str
    score: float
    doc_id: str
    chunk_index: int


class AskResponse(BaseModel):
    """Response containing the AI-generated answer."""
    answer: str
    sources: list[str] = Field(
        description="List of unique source file names used."
    )
    source_details: list[SourceDocument] = Field(
        description="Detailed source chunks with scores."
    )
    query: str
    chunks_retrieved: int


# ── Status / Health ─────────────────────────────────────────

class HealthResponse(BaseModel):
    """System health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    index_stats: Optional[dict] = None


class DocumentListItem(BaseModel):
    """A document in the knowledge base."""
    doc_id: str
    file_name: str
    chunk_count: int
    source: str


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
