"""Test document builders (no extra dependencies)."""

import io


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[str]) -> bytes:
    """Build a minimal valid PDF with one text page per entry (Helvetica)."""
    n = len(pages)
    page_ids = [4 + 2 * i for i in range(n)]
    content_ids = [5 + 2 * i for i in range(n)]
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {n} >>".encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for i, text in enumerate(pages):
        ops = " ".join(f"({_pdf_escape(line)}) Tj T*" for line in text.split("\n"))
        stream = f"BT /F1 11 Tf 14 TL 72 740 Td {ops} ET".encode("latin-1")
        objects[page_ids[i]] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_ids[i]} 0 R >>"
        ).encode()
        objects[content_ids[i]] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode() + objects[num] + b"\nendobj\n"
    xref = len(out)
    size = len(objects) + 1
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for num in range(1, size):
        out += f"{offsets[num]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def make_docx(blocks: list[tuple[str, str]]) -> bytes:
    """Build a .docx. blocks: ("heading", text) | ("para", text) | ("table", "a|b;c|d")."""
    from docx import Document

    doc = Document()
    for kind, text in blocks:
        if kind == "heading":
            doc.add_heading(text, level=1)
        elif kind == "table":
            rows = [r.split("|") for r in text.split(";")]
            table = doc.add_table(rows=len(rows), cols=len(rows[0]))
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    table.cell(r, c).text = value
        else:
            doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


POLICY_TEXT = """REFUND POLICY

Customers may request a full refund within 30 days of purchase if they are unsatisfied.

Refunds are returned to the original payment method within 5 business days.

SHIPPING

Orders ship within 2 business days. Express shipping is available for an extra fee.

SECURITY

All customer data is encrypted at rest using AES-256 and in transit using TLS 1.3.
"""
