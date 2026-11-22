import pytest

from helpers import make_docx, make_pdf
from processing.parser import DocumentParser
from processing.validation import DocumentParseError


@pytest.fixture
def parser():
    return DocumentParser()


def test_clean_text_preserves_paragraph_breaks(parser):
    # Regression: v1 collapsed every "\n\n" into a space, destroying structure.
    raw = "REFUND POLICY\n\nCustomers may request a refund.\n\n\n\nShipping\n\nOrders ship in 2 days."
    cleaned = parser._clean_text(raw)
    assert cleaned.count("\n\n") == 3
    assert "REFUND POLICY\n\nCustomers" in cleaned


def test_clean_text_normalizes_whitespace_and_hyphenation(parser):
    raw = "  Hello   world\t\tagain  \r\nThis is an ex-\nample\x00 text.\x0c"
    cleaned = parser._clean_text(raw)
    assert cleaned == "Hello world again\nThis is an example text."


def test_parse_txt_with_cp1252_encoding(parser, tmp_path):
    path = tmp_path / "notes.txt"
    path.write_bytes("Café prices — 5€".encode("cp1252"))
    assert parser.parse(path) == "Café prices — 5€"


def test_parse_markdown(parser, tmp_path):
    path = tmp_path / "readme.md"
    path.write_text("# Title\n\nBody text here.", encoding="utf-8")
    pages = parser.parse_pages(path)
    assert len(pages) == 1 and pages[0].number is None
    assert pages[0].text == "# Title\n\nBody text here."


def test_parse_docx_keeps_order_headings_and_tables(parser, tmp_path):
    path = tmp_path / "doc.docx"
    path.write_bytes(
        make_docx(
            [
                ("heading", "Pricing"),
                ("para", "Plans are billed monthly."),
                ("table", "Plan|Price;Basic|$0"),
                ("para", "Closing paragraph."),
            ]
        )
    )
    text = parser.parse(path)
    assert text.index("# Pricing") < text.index("Plans are billed") < text.index("Basic | $0") < text.index("Closing")


def test_parse_pdf_returns_numbered_pages(parser, tmp_path):
    path = tmp_path / "doc.pdf"
    path.write_bytes(make_pdf(["First page text about refunds.", "Second page text about shipping."]))
    pages = parser.parse_pages(path)
    assert [p.number for p in pages] == [1, 2]
    assert "refunds" in pages[0].text
    assert "shipping" in pages[1].text


def test_parse_corrupt_pdf_raises_parse_error(parser, tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-1.4\nthis is not really a pdf")
    with pytest.raises(DocumentParseError):
        parser.parse_pages(path)


def test_parse_rejects_legacy_doc_and_unknown_types(parser, tmp_path):
    for name in ("old.doc", "image.png"):
        path = tmp_path / name
        path.write_bytes(b"data")
        with pytest.raises(ValueError):
            parser.parse(path)


def test_parse_missing_file(parser, tmp_path):
    with pytest.raises(FileNotFoundError):
        parser.parse(tmp_path / "missing.txt")
