"""
API Routes
FastAPI endpoints for the Highwatch RAG system.
"""

import os
import uuid
import shutil
import asyncio
from pathlib import Path
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks

from api.models import (
    AskRequest,
    AskResponse,
    SyncRequest,
    SyncResponse,
    HealthResponse,
    DocumentsResponse,
    DocumentListItem,
    SourceDocument,
    UploadResponse,
)
from api.llm_service import LLMService
from config.settings import get_settings
from connectors.gdrive import GoogleDriveConnector
from processing.parser import DocumentParser
from processing.chunker import TextChunker, Chunk
from embedding.embedder import EmbeddingService
from search.vector_store import VectorStore

logger = structlog.get_logger(__name__)
router = APIRouter()

# ── Service Singletons ──────────────────────────────────────

_gdrive: Optional[GoogleDriveConnector] = None
_parser: Optional[DocumentParser] = None
_chunker: Optional[TextChunker] = None
_embedder: Optional[EmbeddingService] = None
_vector_store: Optional[VectorStore] = None
_llm: Optional[LLMService] = None


def get_gdrive() -> GoogleDriveConnector:
    global _gdrive
    if _gdrive is None:
        _gdrive = GoogleDriveConnector()
    return _gdrive


def get_parser() -> DocumentParser:
    global _parser
    if _parser is None:
        _parser = DocumentParser()
    return _parser


def get_chunker() -> TextChunker:
    global _chunker
    if _chunker is None:
        _chunker = TextChunker()
    return _chunker


def get_embedder() -> EmbeddingService:
    global _embedder
    if _embedder is None:
        _embedder = EmbeddingService()
    return _embedder


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def get_llm() -> LLMService:
    global _llm
    if _llm is None:
        _llm = LLMService()
    return _llm


# ── Pipeline Helpers ────────────────────────────────────────

def process_and_index_file(
    file_path: str,
    doc_id: str,
    file_name: str,
) -> int:
    """
    Full pipeline: parse → chunk → embed → store.
    
    Returns:
        Number of chunks indexed.
    """
    parser = get_parser()
    chunker = get_chunker()
    embedder = get_embedder()
    store = get_vector_store()

    # 1. Parse document
    text = parser.parse(file_path)
    if not text.strip():
        logger.warning("No text extracted", file=file_name)
        return 0

    # 2. Chunk text
    chunks = chunker.chunk_document(
        text=text,
        doc_id=doc_id,
        file_name=file_name,
        metadata={"source": "gdrive"},
    )
    if not chunks:
        return 0

    # 3. Generate embeddings (batch)
    texts = [chunk.text for chunk in chunks]
    embeddings = embedder.embed_batch(texts)

    # 4. Store in vector index
    chunk_metadata = [chunk.to_dict() for chunk in chunks]
    store.add(embeddings, chunk_metadata)

    logger.info(
        "Indexed document",
        doc_id=doc_id,
        file_name=file_name,
        chunks=len(chunks),
    )
    return len(chunks)


# ── Endpoints ───────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """System health check endpoint."""
    store = get_vector_store()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        index_stats=store.get_stats(),
    )


@router.post("/sync-drive", response_model=SyncResponse, tags=["Google Drive"])
async def sync_drive(request: SyncRequest = SyncRequest()):
    """
    Sync documents from Google Drive.
    
    Connects to Google Drive, fetches new/updated documents,
    processes them through the RAG pipeline, and indexes them.
    """
    try:
        gdrive = get_gdrive()
        
        # Perform sync (authenticate + fetch)
        sync_result = await asyncio.to_thread(
            gdrive.sync, request.folder_ids
        )

        total_chunks = 0
        files_to_process = sync_result["new_files"] + sync_result["updated_files"]

        # Process new and updated files
        for file_info in files_to_process:
            try:
                doc_id = file_info["id"]
                file_path = file_info["path"]
                file_name = file_info["name"]

                # Delete old vectors for updated files
                if file_info in sync_result.get("updated_files", []):
                    store = get_vector_store()
                    store.delete_by_doc_id(doc_id)

                # Run pipeline
                chunks_created = await asyncio.to_thread(
                    process_and_index_file, file_path, doc_id, file_name
                )
                total_chunks += chunks_created

            except Exception as e:
                logger.error(
                    "Failed to process file",
                    file=file_info.get("name"),
                    error=str(e),
                )
                sync_result["errors"].append({
                    "id": file_info.get("id", ""),
                    "name": file_info.get("name", ""),
                    "error": str(e),
                })

        return SyncResponse(
            status="success",
            message=f"Sync completed. Processed {len(files_to_process)} files, created {total_chunks} chunks.",
            new_files=sync_result["new_files"],
            updated_files=sync_result["updated_files"],
            unchanged_files=sync_result["unchanged_files"],
            errors=sync_result["errors"],
            total_chunks_created=total_chunks,
            timestamp=sync_result["timestamp"],
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Sync failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/ask", response_model=AskResponse, tags=["RAG Query"])
async def ask_question(request: AskRequest):
    """
    Ask a question against the document knowledge base.
    
    Converts query to embedding, retrieves relevant chunks,
    passes context to LLM, and returns a grounded answer with sources.
    """
    try:
        embedder = get_embedder()
        store = get_vector_store()
        llm = get_llm()

        # 1. Embed the query
        query_embedding = await asyncio.to_thread(
            embedder.embed_query, request.query
        )

        # 2. Search for relevant chunks
        filter_meta = None
        if request.filter_source:
            filter_meta = {"file_name": request.filter_source}

        results = store.search(
            query_embedding=query_embedding,
            top_k=request.top_k,
            filter_metadata=filter_meta,
        )

        if not results:
            return AskResponse(
                answer="No relevant documents found for your question. Please sync your Google Drive first using POST /sync-drive.",
                sources=[],
                source_details=[],
                query=request.query,
                chunks_retrieved=0,
            )

        # 3. Generate answer with LLM
        answer = await llm.generate_answer(
            query=request.query,
            context_chunks=results,
        )

        # 4. Build response with sources
        sources = list(set(r.get("file_name", "Unknown") for r in results))
        source_details = [
            SourceDocument(
                file_name=r.get("file_name", "Unknown"),
                chunk_text=r.get("text", "")[:300] + "..." if len(r.get("text", "")) > 300 else r.get("text", ""),
                score=r.get("score", 0.0),
                doc_id=r.get("doc_id", ""),
                chunk_index=r.get("chunk_index", 0),
            )
            for r in results
        ]

        return AskResponse(
            answer=answer,
            sources=sources,
            source_details=source_details,
            query=request.query,
            chunks_retrieved=len(results),
        )

    except Exception as e:
        logger.error("Ask failed", error=str(e), query=request.query)
        raise HTTPException(status_code=500, detail=f"Failed to process question: {str(e)}")


@router.post("/upload", response_model=UploadResponse, tags=["Documents"])
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document directly (without Google Drive).
    Supports PDF, DOCX, and TXT files.
    """
    settings = get_settings()
    
    # Validate file extension
    allowed_extensions = {".pdf", ".docx", ".doc", ".txt"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_extensions)}",
        )

    doc_id = str(uuid.uuid4())
    upload_dir = Path(settings.storage_dir) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / f"{doc_id}_{file.filename}"

    try:
        # Save uploaded file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Process through pipeline
        chunks_created = await asyncio.to_thread(
            process_and_index_file,
            str(file_path),
            doc_id,
            file.filename,
        )

        return UploadResponse(
            status="success",
            message=f"Document processed successfully. Created {chunks_created} chunks.",
            doc_id=doc_id,
            file_name=file.filename,
            chunks_created=chunks_created,
        )

    except Exception as e:
        # Clean up on failure
        if file_path.exists():
            file_path.unlink()
        logger.error("Upload failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/documents", response_model=DocumentsResponse, tags=["Documents"])
async def list_documents():
    """List all documents in the knowledge base."""
    store = get_vector_store()
    
    # Aggregate chunks by document
    doc_map: dict[str, dict] = {}
    for meta in store.metadata:
        doc_id = meta.get("doc_id", "unknown")
        if doc_id not in doc_map:
            doc_map[doc_id] = {
                "doc_id": doc_id,
                "file_name": meta.get("file_name", "Unknown"),
                "chunk_count": 0,
                "source": meta.get("source", "unknown"),
            }
        doc_map[doc_id]["chunk_count"] += 1

    documents = [DocumentListItem(**doc) for doc in doc_map.values()]

    return DocumentsResponse(
        documents=documents,
        total_documents=len(documents),
        total_chunks=store.index.ntotal,
    )


@router.delete("/documents/{doc_id}", tags=["Documents"])
async def delete_document(doc_id: str):
    """Delete a document and its chunks from the knowledge base."""
    store = get_vector_store()
    removed = store.delete_by_doc_id(doc_id)
    
    if removed == 0:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    
    return {
        "status": "success",
        "message": f"Deleted {removed} chunks for document {doc_id}",
        "doc_id": doc_id,
        "chunks_removed": removed,
    }


@router.delete("/clear", tags=["System"])
async def clear_index():
    """Clear all data from the vector store."""
    store = get_vector_store()
    store.clear()
    return {"status": "success", "message": "Vector store cleared"}
