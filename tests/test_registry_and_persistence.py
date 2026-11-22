from pathlib import Path

import numpy as np
import pytest

from persistence.backends import GCSBackend, LocalBackend
from persistence.files import atomic_write, atomic_write_json, read_json
from processing.registry import DocumentRegistry
from search.vector_store import VectorStore


# ── Registry ────────────────────────────────────────────────

def test_registry_crud_and_reload(tmp_path):
    path = tmp_path / "documents.json"
    reg = DocumentRegistry(path, persistence=LocalBackend())
    reg.upsert({"doc_id": "d1", "file_name": "a.txt", "status": "indexed", "content_hash": "h1"})
    reg.update("d1", chunk_count=4)
    assert reg.find_by_hash("h1")["doc_id"] == "d1"
    assert reg.find_by_hash("nope") is None

    again = DocumentRegistry(path, persistence=LocalBackend())
    doc = again.get("d1")
    assert doc["chunk_count"] == 4 and doc["created_at"] and doc["updated_at"]
    assert again.delete("d1")["file_name"] == "a.txt"
    assert len(DocumentRegistry(path, persistence=LocalBackend())) == 0


def test_failed_documents_do_not_count_as_duplicates(tmp_path):
    reg = DocumentRegistry(tmp_path / "r.json", persistence=LocalBackend())
    reg.upsert({"doc_id": "d1", "status": "failed", "content_hash": "h"})
    assert reg.find_by_hash("h") is None


def test_corrupt_registry_is_quarantined(tmp_path):
    path = tmp_path / "documents.json"
    path.write_text("{not json")
    reg = DocumentRegistry(path, persistence=LocalBackend())
    assert len(reg) == 0 and "unreadable" in reg.load_error
    assert list(tmp_path.glob("documents.json.corrupt-*"))


def test_backfill_from_legacy_index(tmp_path):
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "u1_report.pdf").write_bytes(b"%PDF-")
    reg = DocumentRegistry(tmp_path / "r.json", persistence=LocalBackend())
    added = reg.backfill_from_index(
        [{"doc_id": "u1", "file_name": "report.pdf"}, {"doc_id": "u1", "file_name": "report.pdf"},
         {"doc_id": "g1", "file_name": "drive.docx"}],
        tmp_path,
    )
    assert added == 2
    assert reg.get("u1")["chunk_count"] == 2 and reg.get("u1")["stored_path"].endswith("u1_report.pdf")
    assert reg.get("g1")["stored_path"] is None
    assert reg.backfill_from_index([{"doc_id": "u1"}], tmp_path) == 0


# ── Atomic files ────────────────────────────────────────────

def test_atomic_write_keeps_old_file_on_failure(tmp_path):
    target = tmp_path / "data.json"
    atomic_write_json(target, {"v": 1})

    def broken_writer(tmp):
        Path(tmp).write_text("partial")
        raise RuntimeError("disk full")

    with pytest.raises(RuntimeError):
        atomic_write(target, broken_writer)
    assert read_json(target, None) == {"v": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"], "temp file must be cleaned up"


# ── GCS backend (fake bucket, no network, no cost) ─────────

class FakeBlob:
    def __init__(self, bucket, name):
        self.bucket, self.name = bucket, name

    def upload_from_filename(self, filename):
        self.bucket.objects[self.name] = Path(filename).read_bytes()

    def download_to_filename(self, filename):
        Path(filename).write_bytes(self.bucket.objects[self.name])

    def delete(self):
        self.bucket.objects.pop(self.name)


class FakeBucket:
    def __init__(self):
        self.objects = {}

    def blob(self, name):
        return FakeBlob(self, name)

    def list_blobs(self, prefix=""):
        return [FakeBlob(self, n) for n in sorted(self.objects) if n.startswith(prefix)]


class FakeClient:
    def __init__(self):
        self.bucket_obj = FakeBucket()

    def bucket(self, name):
        return self.bucket_obj


def test_gcs_backend_round_trip(tmp_path):
    client = FakeClient()
    src = tmp_path / "src"
    (src / "uploads").mkdir(parents=True)
    f1 = src / "documents.json"
    f2 = src / "uploads" / "x_a.txt"
    f1.write_text("{}")
    f2.write_text("hello")

    backend = GCSBackend("bucket", "app", src, client=client)
    backend.persist(f1, f2, tmp_path / "outside.txt")
    assert set(client.bucket_obj.objects) == {"app/documents.json", "app/uploads/x_a.txt"}

    dest = tmp_path / "dest"
    restored = GCSBackend("bucket", "app", dest, client=client).restore()
    assert restored == 2
    assert (dest / "uploads" / "x_a.txt").read_text() == "hello"

    backend.remove(f2)
    assert "app/uploads/x_a.txt" not in client.bucket_obj.objects


def test_gcs_backend_requires_bucket(tmp_path):
    with pytest.raises(ValueError):
        GCSBackend("", "p", tmp_path, client=FakeClient())


def test_vector_index_survives_restart_via_gcs(env, tmp_path):
    """Simulates Cloud Run: local disk is lost, the bucket restores the index."""
    from config.settings import get_settings

    client = FakeClient()
    settings = get_settings()
    backend = GCSBackend("bucket", "app", settings.storage_dir, client=client)
    store = VectorStore(persistence=backend)
    v = np.zeros((1, 384), dtype=np.float32)
    v[0, 7] = 1
    store.add(v, [{"doc_id": "d", "text": "t", "file_name": "f"}])

    # "New container": wipe local storage, then restore from the bucket.
    for p in Path(settings.storage_dir).rglob("*"):
        if p.is_file():
            p.unlink()
    assert VectorStore(persistence=LocalBackend()).total_vectors == 0
    GCSBackend("bucket", "app", settings.storage_dir, client=client).restore()
    assert VectorStore(persistence=LocalBackend()).total_vectors == 1
