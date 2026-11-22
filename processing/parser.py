"""
Document Parser
Extracts and normalizes text from PDF, DOCX, TXT and Markdown files.

PDFs are returned page by page so answers can cite page numbers.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

from processing.validation import DocumentParseError

logger = structlog.get_logger(__name__)


@dataclass
class PageText:
    """Text of one page. `number` is None for formats without pages."""

    number: Optional[int]
    text: str


class DocumentParser:
    """Extracts text content from various document formats."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

    def parse(self, file_path: str | Path) -> str:
        """Parse a document and return its full cleaned text."""
        return "\n\n".join(p.text for p in self.parse_pages(file_path) if p.text)

    def parse_pages(self, file_path: str | Path) -> list[PageText]:
        """
        Parse a document into cleaned per-page text.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file type is unsupported.
            DocumentParseError: If the file cannot be read.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()
        if ext == ".doc":
            raise ValueError("Legacy .doc files are not supported; convert to .docx")
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}")

        logger.info("Parsing document", file=path.name, type=ext)

        if ext == ".pdf":
            raw_pages = self._extract_pdf(path)
        elif ext == ".docx":
            raw_pages = [PageText(None, self._extract_docx(path))]
        else:
            raw_pages = [PageText(None, self._extract_txt(path))]

        pages = [PageText(p.number, self._clean_text(p.text)) for p in raw_pages]
        logger.info(
            "Parsed document",
            file=path.name,
            pages=len(pages),
            chars=sum(len(p.text) for p in pages),
        )
        return pages

    # ── Extractors ─────────────────────────────────────────

    def _extract_pdf(self, path: Path) -> list[PageText]:
        """Extract per-page text with pdfplumber (falls back to pypdf).

        Table text is already part of page.extract_text(), so tables are not
        extracted separately (that used to index table content twice).
        """
        try:
            import pdfplumber

            pages = []
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    pages.append(PageText(i, page.extract_text() or ""))
            return pages
        except Exception as e:  # noqa: BLE001
            logger.warning("pdfplumber failed, trying pypdf", file=path.name, error=str(e))
            return self._extract_pdf_fallback(path)

    def _extract_pdf_fallback(self, path: Path) -> list[PageText]:
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            if reader.is_encrypted:
                raise DocumentParseError("The PDF is password-protected.")
            return [PageText(i, page.extract_text() or "") for i, page in enumerate(reader.pages, start=1)]
        except DocumentParseError:
            raise
        except Exception as e:  # noqa: BLE001
            raise DocumentParseError(f"Could not read the PDF (it may be corrupt or encrypted): {e}") from e

    def _extract_docx(self, path: Path) -> str:
        """Extract paragraphs and tables from a DOCX in document order.

        Word headings are emitted as Markdown headings so the chunker can track
        sections.
        """
        try:
            from docx import Document as DocxDocument
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            doc = DocxDocument(str(path))
        except Exception as e:  # noqa: BLE001
            raise DocumentParseError(f"Could not read the .docx file: {e}") from e

        parts: list[str] = []
        for child in doc.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                para = Paragraph(child, doc)
                text = para.text.strip()
                if not text:
                    continue
                style = (para.style.name if para.style is not None else "") or ""
                match = re.match(r"Heading (\d)", style)
                if match:
                    text = f"{'#' * min(int(match.group(1)), 6)} {text}"
                elif style == "Title":
                    text = f"# {text}"
                parts.append(text)
            elif tag == "tbl":
                for row in Table(child, doc).rows:
                    cells = []
                    for cell in row.cells:
                        value = cell.text.strip()
                        # Merged cells repeat; keep each value once per row.
                        if value and (not cells or cells[-1] != value):
                            cells.append(value)
                    if cells:
                        parts.append(" | ".join(cells))
        return "\n\n".join(parts)

    def _extract_txt(self, path: Path) -> str:
        """Extract text from plain text / Markdown files."""
        data = path.read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "cp1252"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("latin-1")

    # ── Cleaning ───────────────────────────────────────────

    def _clean_text(self, text: str) -> str:
        """
        Normalize extracted text while keeping paragraph structure.

        - Normalize line endings
        - Remove control characters (keep newlines and tabs)
        - Collapse runs of spaces/tabs (NOT newlines) to a single space
        - Join words hyphenated across line breaks
        - Collapse 3+ newlines to a paragraph break
        """
        if not text:
            return ""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
        text = re.sub(r"[^\S\n]+", " ", text)
        text = "\n".join(line.strip() for line in text.split("\n"))
        text = re.sub(r"(?<=[a-z])-\n(?=[a-z])", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
