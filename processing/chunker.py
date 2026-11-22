"""
Text Chunker
Splits documents into overlapping, structure-aware chunks with metadata.

Strategy:
1. Walk the text line by line, grouping lines into paragraphs and detecting
   headings (Markdown "#", numbered "2.1 Scope", or short ALL-CAPS lines).
   A heading is kept with the paragraph that follows it.
2. Paragraphs longer than CHUNK_SIZE are split at sentence boundaries, and
   over-long sentences at word boundaries.
3. Paragraphs are packed greedily into chunks of up to CHUNK_SIZE characters.
   A new chunk starts at a section/page boundary once the current chunk is at
   least MIN_CHUNK_SIZE long; shorter content is merged, never dropped.
4. Consecutive chunks in the same section share CHUNK_OVERLAP characters of
   context.
"""

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")
_MD_HEADING = re.compile(r"^#{1,6}\s+\S")
_NUMBERED_HEADING = re.compile(r"^\d+(\.\d+)*\.?\s+[A-Z][^.!?]*$")
_CAPS_HEADING = re.compile(r"^[A-Z][A-Z0-9 &/,'()\-:]{3,79}$")


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""

    chunk_id: str
    doc_id: str
    file_name: str
    text: str
    chunk_index: int
    total_chunks: int
    source: str = "upload"
    page: Optional[int] = None
    page_end: Optional[int] = None
    section: Optional[str] = None
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
            "page": self.page,
            "page_end": self.page_end,
            "section": self.section,
            "metadata": self.metadata,
        }


@dataclass
class _Unit:
    page: Optional[int]
    section: Optional[str]
    text: str


@dataclass
class _Draft:
    page: Optional[int]
    page_end: Optional[int]
    section: Optional[str]
    text: str
    overlap_len: int = 0  # chars at the start copied from the previous chunk


class TextChunker:
    """Splits text into overlapping, structure-aware chunks."""

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        min_chunk_size: Optional[int] = None,
    ):
        settings = get_settings()
        self.chunk_size = chunk_size if chunk_size is not None else settings.chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
        self.min_chunk_size = min_chunk_size if min_chunk_size is not None else settings.min_chunk_size
        if self.chunk_size < 100:
            raise ValueError("chunk_size must be at least 100 characters")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

    def chunk_document(
        self,
        text: Optional[str] = None,
        doc_id: str = "",
        file_name: str = "",
        metadata: Optional[dict] = None,
        source: str = "upload",
        pages: Optional[Iterable] = None,
    ) -> list[Chunk]:
        """
        Split a document into chunks.

        Args:
            text: Full document text (used when `pages` is not given).
            doc_id: Unique document identifier.
            file_name: Original file name.
            metadata: Extra metadata copied onto every chunk.
            source: "upload" or "gdrive".
            pages: Optional iterable of (page_number, text) pairs or objects
                with `.number` / `.text` (see processing.parser.PageText).
        """
        page_list = self._normalize_pages(text, pages)
        if not any(t.strip() for _, t in page_list):
            logger.warning("Empty text provided for chunking", doc_id=doc_id)
            return []

        units = self._build_units(page_list)
        drafts = self._pack(units)

        total = len(drafts)
        chunks = [
            Chunk(
                chunk_id=f"{doc_id}:{i}",
                doc_id=doc_id,
                file_name=file_name,
                text=d.text,
                chunk_index=i,
                total_chunks=total,
                source=source,
                page=d.page,
                page_end=d.page_end,
                section=d.section,
                metadata=dict(metadata or {}),
            )
            for i, d in enumerate(drafts)
        ]

        logger.info(
            "Chunked document",
            doc_id=doc_id,
            file_name=file_name,
            total_chunks=total,
            avg_chunk_size=sum(len(c.text) for c in chunks) // max(total, 1),
        )
        return chunks

    # ── Stage 1: paragraphs & headings ─────────────────────

    @staticmethod
    def _normalize_pages(text: Optional[str], pages: Optional[Iterable]) -> list[tuple[Optional[int], str]]:
        if pages is None:
            return [(None, text or "")]
        result = []
        for p in pages:
            if isinstance(p, tuple):
                result.append((p[0], p[1] or ""))
            else:
                result.append((getattr(p, "number", None), getattr(p, "text", "") or ""))
        return result

    @staticmethod
    def _is_heading(line: str) -> bool:
        if len(line) > 80:
            return False
        if _MD_HEADING.match(line):
            return True
        if _NUMBERED_HEADING.match(line):
            return True
        return bool(_CAPS_HEADING.match(line)) and sum(c.isalpha() for c in line) >= 4

    @staticmethod
    def _heading_title(line: str) -> str:
        return line.lstrip("#").strip()

    def _build_units(self, pages: list[tuple[Optional[int], str]]) -> list[_Unit]:
        units: list[_Unit] = []
        section: Optional[str] = None
        pending_heading: Optional[str] = None
        last_page: Optional[int] = None

        def emit(page: Optional[int], body: str) -> None:
            nonlocal pending_heading
            if pending_heading:
                body = f"{pending_heading}\n{body}" if body else pending_heading
                pending_heading = None
            for piece in self._split_oversized(body):
                units.append(_Unit(page, section, piece))

        for page_no, page_text in pages:
            para: list[str] = []
            for raw in page_text.split("\n"):
                line = raw.strip()
                if not line:
                    if para:
                        emit(page_no, "\n".join(para))
                        para = []
                    continue
                if self._is_heading(line):
                    if para:
                        emit(page_no, "\n".join(para))
                        para = []
                    if pending_heading:
                        # Two headings in a row: keep both together.
                        pending_heading = f"{pending_heading}\n{line}"
                    else:
                        pending_heading = line
                    section = self._heading_title(line)
                    continue
                para.append(line)
            if para:
                emit(page_no, "\n".join(para))
            last_page = page_no

        if pending_heading:
            # Heading with no body at the end of the document: keep it.
            units.append(_Unit(last_page, section, pending_heading))
        return units

    def _split_oversized(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]
        pieces: list[str] = []
        current = ""
        for sentence in _SENTENCE_SPLIT.split(text):
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) > self.chunk_size:
                if current:
                    pieces.append(current)
                    current = ""
                pieces.extend(self._hard_split(sentence))
                continue
            candidate = f"{current} {sentence}" if current else sentence
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                pieces.append(current)
                current = sentence
        if current:
            pieces.append(current)
        return pieces

    def _hard_split(self, text: str) -> list[str]:
        """Split text longer than chunk_size at whitespace (or hard if none)."""
        pieces = []
        while len(text) > self.chunk_size:
            cut = text.rfind(" ", 0, self.chunk_size + 1)
            if cut <= self.chunk_size // 2:
                cut = self.chunk_size
            pieces.append(text[:cut].strip())
            text = text[cut:].strip()
        if text:
            pieces.append(text)
        return pieces

    # ── Stage 2: packing with overlap ──────────────────────

    def _pack(self, units: list[_Unit]) -> list[_Draft]:
        drafts: list[_Draft] = []
        current: Optional[_Draft] = None

        for unit in units:
            if current is None:
                current = _Draft(unit.page, unit.page, unit.section, unit.text)
                continue

            section_changed = unit.section != current.section
            page_changed = unit.page != current.page_end
            at_boundary = section_changed or page_changed
            fits = len(current.text) + 2 + len(unit.text) <= self.chunk_size

            if fits and not (at_boundary and len(current.text) >= self.min_chunk_size):
                current.text = f"{current.text}\n\n{unit.text}"
                if unit.page is not None:
                    current.page_end = unit.page
                if current.section is None:
                    current.section = unit.section
                continue

            drafts.append(current)
            prefix = "" if section_changed else self._tail(current.text)
            text = f"{prefix} {unit.text}" if prefix else unit.text
            current = _Draft(unit.page, unit.page, unit.section, text, len(prefix) + 1 if prefix else 0)

        if current is not None:
            drafts.append(current)

        # A tiny trailing chunk is merged into the previous one when possible
        # (dropping its overlap prefix, which the previous chunk already has).
        if len(drafts) >= 2:
            prev, last = drafts[-2], drafts[-1]
            body = last.text[last.overlap_len:]
            if len(body) < self.min_chunk_size and len(prev.text) + 2 + len(body) <= self.chunk_size + self.chunk_overlap:
                prev.text = f"{prev.text}\n\n{body}"
                if last.page_end is not None:
                    prev.page_end = last.page_end
                drafts.pop()
        return drafts

    def _tail(self, text: str) -> str:
        """Last ~chunk_overlap characters of text, starting at a word boundary."""
        if self.chunk_overlap <= 0:
            return ""
        if len(text) <= self.chunk_overlap:
            return text.strip()
        tail = text[-self.chunk_overlap:]
        match = re.search(r"\s", tail)
        if match:
            tail = tail[match.end():]
        return tail.strip()
