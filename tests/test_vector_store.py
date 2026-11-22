import json
import threading
from pathlib import Path

import numpy as np
import pytest

from search.vector_store import VectorStore, VectorStoreError

DIM = 384


def vec(*hot):
    v = np.zeros(DIM, dtype=np.float32)
    for i in hot:
        v[i] = 1.0
    return v


def meta(doc_id, i, **extra):
    return {"doc_id": doc_id, "chunk_index": i, "file_name": f"{doc_id}.txt", "text": f"{doc_id} chunk {i}", **extra}


@pytest.fixture
def store(env):
    return VectorStore()


def test_add_and_search_ranks_by_similarity(store):
    store.add(np.stack([vec(0), vec(1), vec(0, 1)]), [meta("a", 0), meta("b", 0), meta("c", 0)])
    results = store.search(vec(0), top_k=3, min_score=0.0)
    assert [r["doc_id"] for r in results][:2] == ["a", "c"]
    assert results[0]["score"] == pytest.approx(1.0)
    assert results[1]["score"] == pytest.approx(0.7071, abs=1e-3)


def test_threshold_and_filter(store):
    store.add(np.stack([vec(0), vec(1)]), [meta("a", 0), meta("b", 0)])
    assert store.search(vec(2), min_score=0.1) == []
    filtered = store.search(vec(0, 1), top_k=5, filter_metadata={"file_name": "b.txt"}, min_score=0.0)
    assert [r["doc_id"] for r in filtered] == ["b"]


def test_search_empty_index(store):
    assert store.search(vec(0)) == []


def test_delete_keeps_vectors_aligned_with_metadata(store):
    store.add(np.stack([vec(0), vec(1), vec(2)]), [meta("a", 0), meta("b", 0), meta("c", 0)])
    assert store.delete_by_doc_id("b") == 1
    assert store.delete_by_doc_id("missing") == 0
    top = store.search(vec(2), top_k=1, min_score=0.0)[0]
    assert top["doc_id"] == "c" and top["score"] == pytest.approx(1.0)
    assert store.total_vectors == len(store.metadata) == 2


def test_replace_document(store):
    store.add(np.stack([vec(0), vec(1)]), [meta("a", 0), meta("a", 1)])
    store.replace_document("a", np.stack([vec(5)]), [meta("a", 0, text="new")])
    assert store.total_vectors == 1
    assert store.search(vec(5), min_score=0.5)[0]["text"] == "new"


def test_dimension_mismatch_raises(store):
    with pytest.raises(VectorStoreError):
        store.add(np.ones((1, 10), dtype=np.float32), [meta("a", 0)])


def test_persists_across_restarts_with_manifest(env):
    first = VectorStore()
    first.add(np.stack([vec(0), vec(3)]), [meta("a", 0), meta("b", 0)])

    second = VectorStore()
    assert second.total_vectors == 2
    assert second.search(vec(3), top_k=1, min_score=0.0)[0]["doc_id"] == "b"
    manifest = json.loads(Path(second.manifest_path).read_text())
    assert manifest["vectors"] == 2 and manifest["embedding_model"] == second.embedding_model
    assert second.load_error is None


def test_inconsistent_files_are_quarantined_not_deleted(env):
    first = VectorStore()
    first.add(np.stack([vec(0), vec(1)]), [meta("a", 0), meta("b", 0)])
    Path(first.metadata_path).write_text(json.dumps([meta("a", 0)]))  # simulate crash mid-save

    second = VectorStore()
    assert second.total_vectors == 0
    assert "moved aside" in second.load_error
    folder = Path(first.index_file).parent
    assert list(folder.glob("faiss_index.bin.stale-*")), "original index must be kept for inspection"
    # The store is usable again and saving works.
    second.add(np.stack([vec(2)]), [meta("c", 0)])
    assert VectorStore().total_vectors == 1


def test_embedding_model_change_is_detected(env):
    VectorStore(embedding_model="model-a").add(np.stack([vec(0)]), [meta("a", 0)])
    store = VectorStore(embedding_model="model-b")
    assert store.total_vectors == 0
    assert "model-a" in store.load_error


def test_legacy_index_without_manifest_loads(env):
    first = VectorStore()
    first.add(np.stack([vec(0)]), [meta("a", 0)])
    Path(first.manifest_path).unlink()
    assert VectorStore().total_vectors == 1


def test_concurrent_adds_stay_consistent(env):
    store = VectorStore()

    def worker(n):
        for i in range(15):
            store.add(np.stack([vec(n)]), [meta(f"t{n}", i)])

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert store.total_vectors == len(store.metadata) == 90
    reloaded = VectorStore()
    assert reloaded.total_vectors == 90 and reloaded.load_error is None
    for m, i in zip(reloaded.metadata, range(90)):
        assert m["doc_id"].startswith("t")


def test_stats_do_not_leak_document_ids(store):
    store.add(np.stack([vec(0)]), [meta("secret-doc", 0)])
    stats = store.get_stats()
    assert stats["unique_documents"] == 1
    assert "secret-doc" not in json.dumps(stats)
