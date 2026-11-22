import re

import pytest

from processing.chunker import TextChunker
from processing.parser import PageText


@pytest.fixture
def chunker(env):
    return TextChunker(chunk_size=300, chunk_overlap=50, min_chunk_size=80)


def _words(text):
    return re.findall(r"\w+", text)


def test_short_sections_are_kept_not_dropped(chunker):
    # Regression: v1 silently dropped sections shorter than MIN_CHUNK_SIZE.
    text = "Refund window: 30 days.\n\nShipping: 2 days.\n\nThis is a much longer paragraph that easily exceeds the minimum size."
    chunks = chunker.chunk_document(text, doc_id="d1", file_name="f.txt")
    joined = "\n".join(c.text for c in chunks)
    assert "Refund window: 30 days." in joined
    assert "Shipping: 2 days." in joined


def test_tiny_document_produces_one_chunk(chunker):
    chunks = chunker.chunk_document("Only one fact.", doc_id="d", file_name="f.txt")
    assert len(chunks) == 1 and chunks[0].text == "Only one fact."


def test_no_text_is_lost_and_sizes_are_bounded(chunker):
    paragraphs = [
        " ".join(f"Sentence {p}-{s} talks about topic {p} in detail." for s in range(1, 9))
        for p in range(1, 13)
    ]
    text = "\n\n".join(paragraphs)
    chunks = chunker.chunk_document(text, doc_id="d", file_name="f.txt")

    assert len(chunks) > 3
    all_chunk_words = set(w for c in chunks for w in _words(c.text))
    for p in range(1, 13):
        for s in range(1, 9):
            assert f"{p}" in all_chunk_words
            assert any(f"Sentence {p}-{s} " in c.text for c in chunks), f"lost sentence {p}-{s}"
    for c in chunks:
        assert len(c.text) <= chunker.chunk_size + chunker.chunk_overlap + 1


def test_consecutive_chunks_overlap(chunker):
    text = " ".join(f"Word{i} is here." for i in range(200))
    chunks = chunker.chunk_document(text, doc_id="d", file_name="f.txt")
    assert len(chunks) >= 3
    for prev, cur in zip(chunks, chunks[1:]):
        tail_words = prev.text.split()[-3:]
        assert " ".join(tail_words) in cur.text


def test_sections_tracked_and_heading_kept_with_body(chunker):
    text = (
        "REFUND POLICY\n\n" + "Refunds are available within 30 days of purchase. " * 3
        + "\n\n## Shipping\n\n" + "Orders ship in two business days from our warehouse. " * 3
    )
    chunks = chunker.chunk_document(text, doc_id="d", file_name="f.md")
    sections = {c.section for c in chunks}
    assert {"REFUND POLICY", "Shipping"} <= sections
    first_shipping = next(c for c in chunks if c.section == "Shipping")
    assert first_shipping.text.startswith("## Shipping")
    # No overlap is carried across a section change.
    assert "Refunds" not in first_shipping.text


def test_page_numbers_recorded(chunker):
    pages = [
        PageText(1, "Page one talks about refunds and the refund window in detail. " * 2),
        PageText(2, "Page two talks about shipping speeds and carriers in detail. " * 2),
    ]
    chunks = chunker.chunk_document(doc_id="d", file_name="f.pdf", pages=pages)
    refund = next(c for c in chunks if "refund" in c.text)
    shipping = next(c for c in chunks if "shipping" in c.text and c.page == 2)
    assert refund.page == 1
    assert shipping.page == 2


def test_ids_deterministic_and_source_propagated(chunker):
    text = "A paragraph about something important enough to index. " * 10
    a = chunker.chunk_document(text, doc_id="doc-9", file_name="f.txt", source="gdrive", metadata={"url": "u"})
    b = chunker.chunk_document(text, doc_id="doc-9", file_name="f.txt", source="gdrive")
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b] == [f"doc-9:{i}" for i in range(len(a))]
    assert all(c.source == "gdrive" for c in a)
    assert a[0].to_dict()["metadata"] == {"url": "u"}
    assert a[-1].total_chunks == len(a)


def test_empty_text_returns_no_chunks(chunker):
    assert chunker.chunk_document("   \n\n  ", doc_id="d", file_name="f") == []


def test_invalid_configuration_rejected(env):
    with pytest.raises(ValueError):
        TextChunker(chunk_size=200, chunk_overlap=200)
