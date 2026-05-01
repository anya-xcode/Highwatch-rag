"""
Text Chunker
Splits documents into meaningful, overlapping segments with metadata.
Implements a semantic-aware chunking strategy.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""
    chunk_id: str
    doc_id: str
    file_name: str
    text: str
    chunk_index: int
    total_chunks: int
    source: str = "gdrive"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "file_name": self.file_name,
            "text": self.text,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "source": self.source,
            "metadata": self.metadata,
        }


class TextChunker:
    """
    Splits text into overlapping, semantically-aware chunks.
    
    Strategy:
    1. First split by major section boundaries (headings, double newlines)
    2. If sections are too large, split by paragraph
    3. If paragraphs are too large, split by sentence
    4. Apply overlap between consecutive chunks for context continuity
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        min_chunk_size: Optional[int] = None,
    ):
        settings = get_settings()
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.min_chunk_size = min_chunk_size or settings.min_chunk_size

    def chunk_document(
        self,
        text: str,
        doc_id: str,
        file_name: str,
        metadata: Optional[dict] = None,
    ) -> list[Chunk]:
        """
        Split document text into chunks with metadata.
        
        Args:
            text: Full document text.
            doc_id: Unique document identifier.
            file_name: Original file name.
            metadata: Additional metadata to attach.
            
        Returns:
            List of Chunk objects.
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for chunking", doc_id=doc_id)
            return []

        # Split into sections first
        sections = self._split_into_sections(text)
        
        # Process each section into appropriately sized chunks
        raw_chunks = []
        for section in sections:
            if len(section) <= self.chunk_size:
                if len(section.strip()) >= self.min_chunk_size:
                    raw_chunks.append(section.strip())
            else:
                # Further split large sections
                sub_chunks = self._split_large_section(section)
                raw_chunks.extend(sub_chunks)

        # Apply overlap between consecutive chunks
        overlapped_chunks = self._apply_overlap(raw_chunks)

        # Filter out chunks that are too small
        overlapped_chunks = [
            c for c in overlapped_chunks if len(c.strip()) >= self.min_chunk_size
        ]

        # Create Chunk objects
        total = len(overlapped_chunks)
        chunks = []
        for i, chunk_text in enumerate(overlapped_chunks):
            chunk = Chunk(
                chunk_id=str(uuid.uuid4()),
                doc_id=doc_id,
                file_name=file_name,
                text=chunk_text.strip(),
                chunk_index=i,
                total_chunks=total,
                source="gdrive",
                metadata=metadata or {},
            )
            chunks.append(chunk)

        logger.info(
            "Chunked document",
            doc_id=doc_id,
            file_name=file_name,
            total_chunks=total,
            avg_chunk_size=sum(len(c.text) for c in chunks) // max(len(chunks), 1),
        )
        return chunks

    def _split_into_sections(self, text: str) -> list[str]:
        """Split text by major section boundaries."""
        # Split by headings (markdown-style or numbered sections)
        section_pattern = r"\n(?=#{1,6}\s|(?:\d+\.)+\s|[A-Z][A-Z\s]{4,}(?:\n|$))"
        sections = re.split(section_pattern, text)

        # If we got only one section, try splitting by double newlines
        if len(sections) <= 1:
            sections = text.split("\n\n")

        return [s for s in sections if s.strip()]

    def _split_large_section(self, text: str) -> list[str]:
        """Split a large section into smaller chunks by paragraph, then sentence."""
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph stays within limit, add it
            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk = (
                    f"{current_chunk}\n\n{para}" if current_chunk else para
                )
            else:
                # Save current chunk if it has content
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())

                # If paragraph itself is too large, split by sentences
                if len(para) > self.chunk_size:
                    sentence_chunks = self._split_by_sentences(para)
                    chunks.extend(sentence_chunks)
                    current_chunk = ""
                else:
                    current_chunk = para

        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _split_by_sentences(self, text: str) -> list[str]:
        """Split text by sentence boundaries."""
        # Sentence boundary detection
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
        
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                current_chunk = (
                    f"{current_chunk} {sentence}" if current_chunk else sentence
                )
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                
                # If single sentence is too large, force-split by character limit
                if len(sentence) > self.chunk_size:
                    for i in range(0, len(sentence), self.chunk_size):
                        chunk = sentence[i : i + self.chunk_size]
                        if chunk.strip():
                            chunks.append(chunk.strip())
                    current_chunk = ""
                else:
                    current_chunk = sentence

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        """Apply overlap between consecutive chunks for context continuity."""
        if not chunks or self.chunk_overlap <= 0:
            return chunks

        overlapped = [chunks[0]]

        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            current_chunk = chunks[i]

            # Get the tail of previous chunk as overlap prefix
            overlap_text = prev_chunk[-self.chunk_overlap :]

            # Find a clean break point (word boundary)
            space_idx = overlap_text.find(" ")
            if space_idx > 0:
                overlap_text = overlap_text[space_idx + 1 :]

            # Prepend overlap to current chunk
            combined = f"{overlap_text} {current_chunk}"

            # Ensure we don't exceed chunk size
            if len(combined) > self.chunk_size + self.chunk_overlap:
                combined = combined[: self.chunk_size + self.chunk_overlap]

            overlapped.append(combined)

        return overlapped
