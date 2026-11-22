import pytest

from helpers import make_docx, make_pdf
from processing.validation import DocumentValidationError, sanitize_filename, validate_document

ALLOWED = {".pdf", ".docx", ".txt", ".md"}
MAX = 1024 * 1024


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\me\\secret plan.docx", "secret plan.docx"),
        ("weird<>:|?*name.txt", "weird_name.txt"),
        ("", "document"),
        (None, "document"),
        ("...", "document"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_truncates_but_keeps_extension():
    name = sanitize_filename("a" * 300 + ".pdf")
    assert len(name) == 150 and name.endswith(".pdf")


def test_valid_documents_pass():
    assert validate_document("a.pdf", make_pdf(["hi"]), ALLOWED, MAX) == ".pdf"
    assert validate_document("a.docx", make_docx([("para", "hi")]), ALLOWED, MAX) == ".docx"
    assert validate_document("a.txt", b"hello", ALLOWED, MAX) == ".txt"
    assert validate_document("a.MD", b"# hi", ALLOWED, MAX) == ".md"


@pytest.mark.parametrize(
    "name, data, status, fragment",
    [
        ("old.doc", b"x", 400, "Legacy .doc"),
        ("photo.png", b"x", 400, "Unsupported file type"),
        ("noext", b"x", 400, "Unsupported file type"),
        ("empty.txt", b"", 400, "empty"),
        ("big.txt", b"x" * (MAX + 1), 413, "too large"),
        ("fake.pdf", b"hello world", 400, "valid PDF"),
        ("fake.docx", b"hello world", 400, "valid .docx"),
        ("zip.docx", b"PK\x03\x04garbage", 400, "corrupt"),
        ("binary.txt", b"abc\x00\x01\x02", 400, "binary"),
    ],
)
def test_invalid_documents_rejected(name, data, status, fragment):
    with pytest.raises(DocumentValidationError) as exc:
        validate_document(name, data, ALLOWED, MAX)
    assert exc.value.status_code == status
    assert fragment.lower() in exc.value.message.lower()
