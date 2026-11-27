import json
from pathlib import Path

import numpy as np
import pytest

from api.llm_service import LLMService
from config.settings import get_settings
from helpers import POLICY_TEXT, make_docx, make_pdf
from search.vector_store import VectorStore
from test_llm_service import FakeGroq, groq_settings


def upload(client, name, data, content_type="application/octet-stream"):
    return client.post("/api/v1/upload", files={"file": (name, data, content_type)})


def ask(client, query, **extra):
    return client.post("/api/v1/ask", json={"query": query, **extra})


# ── System endpoints ────────────────────────────────────────

def test_health_ready_and_config(make_client):
    client, _ = make_client()
    health = client.get("/health").json()
    assert health["status"] == "healthy" and health["version"] == "2.0.0"
    assert client.get("/api/v1/health").status_code == 200

    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200 and ready.json()["status"] == "ready"

    config = client.get("/api/v1/config").json()
    assert config["llm_provider"] == "extractive"
    assert config["allowed_extensions"] == [".docx", ".md", ".pdf", ".txt"]
    assert config["auth_required"] is False


def test_ready_reports_missing_llm_key_as_degraded(make_client, env):
    env.setenv("LLM_PROVIDER", "groq")
    get_settings.cache_clear()
    client, _ = make_client()
    body = client.get("/api/v1/health/ready").json()
    assert body["status"] == "degraded"
    assert body["checks"]["llm"]["error"] == "GROQ_API_KEY is not set"


def test_frontend_served(make_client):
    client, _ = make_client()
    page = client.get("/")
    assert "Highwatch" in page.text
    assert page.headers["cache-control"] == "no-cache"  # browsers must not run a stale UI
    script = client.get("/static/app.js")
    assert script.status_code == 200 and script.headers["cache-control"] == "no-cache"
    assert "cache-control" not in client.get("/api/v1/health").headers


# ── Upload ──────────────────────────────────────────────────

def test_upload_txt_docx_pdf_and_list(make_client):
    client, _ = make_client()
    r1 = upload(client, "policy.txt", POLICY_TEXT.encode())
    r2 = upload(client, "plan.docx", make_docx([("heading", "Plan"), ("para", "The roadmap ships in March.")]))
    r3 = upload(client, "manual.pdf", make_pdf(["Install the agent first.", "Then configure the dashboard."]))
    for r in (r1, r2, r3):
        assert r.status_code == 200, r.text
        assert r.json()["chunks_created"] >= 1
        assert r.json()["document"]["status"] == "indexed"

    docs = client.get("/api/v1/documents").json()
    assert docs["total_documents"] == 3
    by_name = {d["file_name"]: d for d in docs["documents"]}
    assert by_name["manual.pdf"]["page_count"] == 2
    assert all(d["source"] == "upload" for d in docs["documents"])
    assert docs["total_chunks"] == sum(d["chunk_count"] for d in docs["documents"])

    one = client.get(f"/api/v1/documents/{r1.json()['doc_id']}").json()
    assert one["file_name"] == "policy.txt" and one["size_bytes"] == len(POLICY_TEXT.encode())


@pytest.mark.parametrize(
    "name, data, status, fragment",
    [
        ("virus.exe", b"MZ", 400, "Unsupported"),
        ("old.doc", b"\xd0\xcf\x11\xe0", 400, "Legacy .doc"),
        ("empty.txt", b"", 400, "empty"),
        ("fake.pdf", b"not a pdf", 400, "valid PDF"),
        ("blank.pdf", make_pdf([""]), 422, "No extractable text"),
    ],
)
def test_upload_rejections(make_client, name, data, status, fragment):
    client, services = make_client()
    r = upload(client, name, data)
    assert r.status_code == status, r.text
    assert fragment.lower() in r.json()["detail"].lower()
    # Nothing is left behind.
    assert client.get("/api/v1/documents").json()["total_documents"] == 0
    assert not any(get_settings().uploads_dir.iterdir())


def test_upload_too_large(make_client, env):
    env.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    client, _ = make_client()
    r = upload(client, "big.txt", b"a" * (1024 * 1024 + 10))
    assert r.status_code == 413


def test_upload_content_length_guard(make_client, env):
    env.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    client, _ = make_client()
    r = client.post(
        "/api/v1/upload",
        content=b"x",
        headers={"content-length": str(50 * 1024 * 1024), "content-type": "multipart/form-data; boundary=x"},
    )
    assert r.status_code == 413


def test_duplicate_upload_rejected(make_client):
    client, _ = make_client()
    first = upload(client, "policy.txt", POLICY_TEXT.encode())
    second = upload(client, "policy-copy.txt", POLICY_TEXT.encode())
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["doc_id"] == first.json()["doc_id"] and detail["file_name"] == "policy.txt"
    assert client.get("/api/v1/documents").json()["total_documents"] == 1


def test_filename_is_sanitized(make_client):
    client, _ = make_client()
    r = upload(client, "../../evil.txt", b"Some harmless content about refunds and returns.")
    assert r.status_code == 200 and r.json()["file_name"] == "evil.txt"
    stored = list(get_settings().uploads_dir.iterdir())
    assert len(stored) == 1 and stored[0].name.endswith("_evil.txt")


# ── Ask ─────────────────────────────────────────────────────

def test_ask_with_no_documents(make_client):
    client, _ = make_client()
    body = ask(client, "What is the refund policy?").json()
    assert body["answer_status"] == "no_documents" and body["sources"] == []


def test_ask_extractive_returns_citations(make_client):
    client, _ = make_client()
    upload(client, "policy.txt", POLICY_TEXT.encode())
    body = ask(client, "How many days do I have to request a refund?").json()
    assert body["answer_status"] == "extractive"
    assert body["citations"][0]["file_name"] == "policy.txt"
    assert "30 days" in body["citations"][0]["snippet"]
    assert body["citations"][0]["number"] == 1
    assert body["sources"] == ["policy.txt"]
    assert "[1]" in body["answer"]


def test_ask_with_llm_maps_citations_to_sources(make_client):
    fake = FakeGroq("You can request a refund within 30 days [1].")
    client, _ = make_client(llm=LLMService(groq_settings(), groq_client=fake))
    upload(client, "policy.txt", POLICY_TEXT.encode())
    upload(client, "pdfdoc.pdf", make_pdf(["Refund requests are handled by the billing team."]))
    body = ask(client, "refund request days").json()

    assert body["answer_status"] == "answered"
    assert body["answer"] == "You can request a refund within 30 days [1]."
    assert [c["number"] for c in body["citations"]] == [1]
    cited = body["citations"][0]
    assert cited["file_name"] == body["source_details"][0]["file_name"]
    assert body["sources"] == [cited["file_name"]]
    assert body["provider"] == "groq" and body["model"] == "openai/gpt-oss-120b"
    # The model received numbered excerpts.
    assert '<excerpt id="1"' in fake.calls[0]["messages"][1]["content"]


def test_ask_unrelated_question_is_insufficient_without_llm_call(make_client):
    fake = FakeGroq("should not be called")
    client, _ = make_client(llm=LLMService(groq_settings(), groq_client=fake))
    upload(client, "policy.txt", POLICY_TEXT.encode())
    body = ask(client, "Who won the football world cup?").json()
    assert body["answer_status"] == "insufficient_context"
    assert body["sources"] == [] and body["citations"] == []
    assert "couldn't find" in body["answer"]
    assert fake.calls == []


def test_ask_llm_says_insufficient(make_client):
    client, _ = make_client(llm=LLMService(groq_settings(), groq_client=FakeGroq("INSUFFICIENT_CONTEXT")))
    upload(client, "policy.txt", POLICY_TEXT.encode())
    body = ask(client, "What is the refund fee in euros?").json()
    assert body["answer_status"] == "insufficient_context"
    assert body["sources"] == [] and body["citations"] == []
    assert body["chunks_retrieved"] >= 1  # retrieval happened, but the answer isn't there


def test_ask_llm_failure_is_explicit(make_client):
    failing = FakeGroq(error=RuntimeError("Error code: 429 - rate limit"))
    client, _ = make_client(llm=LLMService(groq_settings(), groq_client=failing))
    upload(client, "policy.txt", POLICY_TEXT.encode())
    body = ask(client, "refund days").json()
    assert body["answer_status"] == "llm_error"
    assert "429" in body["warning"] and "failed" in body["warning"]
    assert body["citations"] and "[1]" in body["answer"]


def test_ask_uncited_answer_gets_warning(make_client):
    client, _ = make_client(llm=LLMService(groq_settings(), groq_client=FakeGroq("Thirty days.")))
    upload(client, "policy.txt", POLICY_TEXT.encode())
    body = ask(client, "refund days").json()
    assert body["answer_status"] == "answered" and body["citations"] == []
    assert "no citations" in body["warning"]
    assert body["sources"] == ["policy.txt"]


def test_ask_validation(make_client):
    client, _ = make_client()
    assert ask(client, "hi").status_code == 422
    assert ask(client, "valid question", top_k=50).status_code == 422


def test_filter_source(make_client):
    client, _ = make_client()
    upload(client, "a.txt", b"Refund policy for product A is 10 days.")
    upload(client, "b.txt", b"Refund policy for product B is 60 days.")
    body = ask(client, "refund policy", filter_source="b.txt").json()
    assert {c["file_name"] for c in body["citations"]} == {"b.txt"}


# ── Delete / clear / reindex ────────────────────────────────

def test_delete_document(make_client):
    client, _ = make_client()
    doc_id = upload(client, "policy.txt", POLICY_TEXT.encode()).json()["doc_id"]
    r = client.delete(f"/api/v1/documents/{doc_id}")
    assert r.status_code == 200 and r.json()["chunks_removed"] >= 1
    assert client.get(f"/api/v1/documents/{doc_id}").status_code == 404
    assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 404
    assert not any(get_settings().uploads_dir.iterdir())
    # Re-uploading the same content works after deletion.
    assert upload(client, "policy.txt", POLICY_TEXT.encode()).status_code == 200


def test_clear_resets_everything(make_client):
    client, services = make_client()
    upload(client, "policy.txt", POLICY_TEXT.encode())
    services.gdrive.commit("drive-file", {"name": "x", "modifiedTime": "t", "hash": "h"})
    r = client.delete("/api/v1/clear").json()
    assert r["status"] == "success" and r["files_removed"] == 1
    assert client.get("/api/v1/documents").json()["total_documents"] == 0
    assert services.store.total_vectors == 0
    # Regression: v1 kept the Drive sync state, so files were never re-synced.
    assert json.loads(get_settings().sync_state_path.read_text()) == {}


def test_persistence_across_restart(make_client):
    client, _ = make_client()
    upload(client, "policy.txt", POLICY_TEXT.encode())
    before = ask(client, "refund days").json()

    restarted, services = make_client()  # brand-new services loading from disk
    assert services.store.total_vectors > 0
    assert restarted.get("/api/v1/documents").json()["total_documents"] == 1
    after = ask(restarted, "refund days").json()
    assert after["citations"][0]["snippet"] == before["citations"][0]["snippet"]


def test_recovery_from_corrupt_index_via_reindex(make_client):
    client, services = make_client()
    upload(client, "policy.txt", POLICY_TEXT.encode())
    upload(client, "manual.pdf", make_pdf(["Install the agent first."]))
    Path(services.store.metadata_path).write_text("[]")  # corrupt: count mismatch

    restarted, services2 = make_client()
    ready = restarted.get("/api/v1/health/ready").json()
    assert ready["status"] == "degraded" and ready["checks"]["vector_store"]["error"]
    assert ask(restarted, "refund days").json()["answer_status"] == "no_documents"

    result = restarted.post("/api/v1/reindex").json()
    assert result["status"] == "success" and len(result["reindexed"]) == 2
    assert ask(restarted, "refund days").json()["answer_status"] == "extractive"


def test_reindex_reports_missing_originals(make_client):
    client, _ = make_client()
    doc_id = upload(client, "policy.txt", POLICY_TEXT.encode()).json()["doc_id"]
    for p in get_settings().uploads_dir.iterdir():
        p.unlink()
    result = client.post("/api/v1/reindex").json()
    assert result["status"] == "partial" and result["failed"][0]["doc_id"] == doc_id
    assert client.get(f"/api/v1/documents/{doc_id}").json()["status"] == "failed"


def test_legacy_index_documents_are_listed(make_client, fake_embedder):
    # Build a v1-style index (no registry, no manifest) before the app starts.
    store = VectorStore()
    store.add(fake_embedder.embed_passages(["legacy refund text"]),
              [{"doc_id": "old-1", "file_name": "old.pdf", "text": "legacy refund text", "chunk_index": 0}])
    Path(store.manifest_path).unlink()
    Path(get_settings().documents_db_path).unlink(missing_ok=True)

    client, _ = make_client()
    docs = client.get("/api/v1/documents").json()["documents"]
    assert [(d["doc_id"], d["status"], d["chunk_count"]) for d in docs] == [("old-1", "indexed", 1)]


# ── API key ─────────────────────────────────────────────────

def test_api_key_protects_everything_but_health(make_client, env):
    env.setenv("API_KEY", "s3cret")
    get_settings.cache_clear()
    client, _ = make_client()

    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health/ready").status_code == 200
    assert client.get("/api/v1/config").json()["auth_required"] is True

    assert ask(client, "refund days").status_code == 401
    assert client.get("/api/v1/documents").status_code == 401
    assert client.delete("/api/v1/clear").status_code == 401
    assert client.get("/api/v1/documents", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/v1/documents", headers={"X-API-Key": "s3cret"}).status_code == 200
