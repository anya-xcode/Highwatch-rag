"""
Upload validation: file names, extensions, size limits and content sniffing.
"""

import io
import re
import unicodedata
import zipfile
from pathlib import Path


class DocumentValidationError(ValueError):
    """A document was rejected. `status_code` is the HTTP status to return."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DocumentParseError(ValueError):
    """A document passed validation but no usable text could be extracted."""


def sanitize_filename(name: str | None) -> str:
    """Strip directories and unusual characters from a client-supplied file name."""
    name = (name or "").replace("\\", "/").split("/")[-1]
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[^\w.\- ()\[\]]+", "_", name).strip(" .")
    if len(name) > 150:
        stem, ext = Path(name).stem, Path(name).suffix
        name = stem[: 150 - len(ext)] + ext
    return name or "document"


def validate_document(file_name: str, data: bytes, allowed_extensions: set[str], max_bytes: int) -> str:
    """
    Validate an uploaded document. Returns the normalized extension.

    Raises:
        DocumentValidationError: with a user-facing message and HTTP status.
    """
    ext = Path(file_name).suffix.lower()

    if ext == ".doc":
        raise DocumentValidationError(
            "Legacy .doc files are not supported. Save the file as .docx and upload it again."
        )
    if ext not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise DocumentValidationError(f"Unsupported file type '{ext or 'none'}'. Allowed: {allowed}.")
    if len(data) == 0:
        raise DocumentValidationError("The file is empty.")
    if len(data) > max_bytes:
        raise DocumentValidationError(
            f"File is too large ({len(data) / 1_048_576:.1f} MB). Maximum is {max_bytes // 1_048_576} MB.",
            status_code=413,
        )

    if ext == ".pdf":
        if b"%PDF-" not in data[:1024]:
            raise DocumentValidationError("The file does not look like a valid PDF.")
    elif ext == ".docx":
        if not data.startswith(b"PK\x03\x04"):
            raise DocumentValidationError("The file does not look like a valid .docx document.")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                if "word/document.xml" not in zf.namelist():
                    raise DocumentValidationError("The .docx file has no document body.")
        except zipfile.BadZipFile:
            raise DocumentValidationError("The .docx file is corrupt.") from None
    elif ext in {".txt", ".md"}:
        sample = data[:8192]
        if b"\x00" in sample:
            raise DocumentValidationError("The file looks binary, not plain text.")

    return ext
