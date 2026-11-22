"""Google Drive sync logic against an in-memory fake Drive (no network, no OAuth)."""

import pytest

from config.settings import get_settings
from connectors.gdrive import DriveAuthError, DriveFileTooLarge, GoogleDriveConnector
from helpers import POLICY_TEXT, make_pdf
from processing.pipeline import run_drive_sync


class FakeDriveConnector(GoogleDriveConnector):
    """Overrides only the network calls; all sync bookkeeping is the real code."""

    def __init__(self):
        super().__init__(service=object())
        self.files: dict[str, dict] = {}

    def put(self, file_id, name, content: bytes, modified="2026-01-01T00:00:00Z", mime="text/plain"):
        self.files[file_id] = {
            "id": file_id,
            "name": name,
            "mimeType": mime,
            "modifiedTime": modified,
            "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
            "_content": content,
        }

    def list_files(self, folder_id=None, page_size=100):
        return [dict(f) for f in self.files.values()]

    def download_file(self, file_metadata):
        path = self._download_dir / f"{file_metadata['id']}_{file_metadata['name']}"
        path.write_bytes(self.files[file_metadata["id"]]["_content"])
        return path


@pytest.fixture
def drive(make_client):
    connector = FakeDriveConnector()
    client, services = make_client()
    services._gdrive = connector
    return client, services, connector


def sync(client):
    r = client.post("/api/v1/sync-drive")
    assert r.status_code == 200, r.text
    return r.json()


def test_initial_sync_indexes_and_links_files(drive):
    client, services, connector = drive
    connector.put("f1", "policy.txt", POLICY_TEXT.encode())
    connector.put("f2", "manual.pdf", make_pdf(["Install the agent."]), mime="application/pdf")

    result = sync(client)
    assert {f["id"] for f in result["new_files"]} == {"f1", "f2"}
    assert result["total_chunks_created"] >= 2 and result["errors"] == []

    docs = {d["doc_id"]: d for d in client.get("/api/v1/documents").json()["documents"]}
    assert docs["f1"]["source"] == "gdrive" and docs["f1"]["url"].endswith("/f1/view")

    body = client.post("/api/v1/ask", json={"query": "refund days"}).json()
    assert body["citations"][0]["url"] == "https://drive.google.com/file/d/f1/view"
    assert body["citations"][0]["source"] == "gdrive"


def test_second_sync_is_unchanged(drive):
    client, _, connector = drive
    connector.put("f1", "policy.txt", POLICY_TEXT.encode())
    sync(client)
    result = sync(client)
    assert result["new_files"] == [] and [f["id"] for f in result["unchanged_files"]] == ["f1"]


def test_modified_file_is_reindexed_without_duplicates(drive):
    client, services, connector = drive
    connector.put("f1", "policy.txt", b"Refunds are allowed within 30 days.")
    sync(client)
    connector.put("f1", "policy.txt", b"Refunds are allowed within 45 days.", modified="2026-02-01T00:00:00Z")
    result = sync(client)
    assert [f["id"] for f in result["updated_files"]] == ["f1"]
    assert services.store.chunk_counts() == {"f1": 1}
    snippet = client.post("/api/v1/ask", json={"query": "refund days"}).json()["citations"][0]["snippet"]
    assert "45 days" in snippet


def test_touched_but_identical_file_is_unchanged(drive):
    client, _, connector = drive
    connector.put("f1", "policy.txt", POLICY_TEXT.encode())
    sync(client)
    connector.put("f1", "policy.txt", POLICY_TEXT.encode(), modified="2026-03-01T00:00:00Z")
    result = sync(client)
    assert result["updated_files"] == [] and [f["id"] for f in result["unchanged_files"]] == ["f1"]


def test_failed_file_is_retried_next_sync(drive):
    # Regression: v1 saved sync state before indexing, so failures were never retried.
    client, services, connector = drive
    connector.put("bad", "scan.pdf", make_pdf([""]), mime="application/pdf")
    first = sync(client)
    assert first["status"] == "partial" and first["errors"][0]["id"] == "bad"
    assert "bad" not in services.gdrive.state
    assert client.get("/api/v1/documents/bad").json()["status"] == "failed"

    connector.put("bad", "scan.pdf", make_pdf(["Now it has text about refunds."]), mime="application/pdf")
    second = sync(client)
    assert [f["id"] for f in second["new_files"]] == ["bad"]
    assert client.get("/api/v1/documents/bad").json()["status"] == "indexed"


def test_deleted_drive_file_is_removed_from_index(drive):
    client, services, connector = drive
    connector.put("f1", "policy.txt", POLICY_TEXT.encode())
    connector.put("f2", "other.txt", b"Other document about shipping speeds.")
    sync(client)
    del connector.files["f2"]
    result = sync(client)
    assert [f["id"] for f in result["removed_files"]] == ["f2"]
    assert services.store.doc_ids() == {"f1"}
    assert client.get("/api/v1/documents/f2").status_code == 404


def test_resync_after_clear(drive):
    client, services, connector = drive
    connector.put("f1", "policy.txt", POLICY_TEXT.encode())
    sync(client)
    client.delete("/api/v1/clear")
    result = sync(client)
    assert [f["id"] for f in result["new_files"]] == ["f1"]
    assert services.store.total_vectors > 0


def test_deleting_drive_doc_lets_next_sync_restore_it(drive):
    client, _, connector = drive
    connector.put("f1", "policy.txt", POLICY_TEXT.encode())
    sync(client)
    client.delete("/api/v1/documents/f1")
    assert [f["id"] for f in sync(client)["new_files"]] == ["f1"]


def test_reindex_with_missing_drive_original_resyncs(drive):
    client, _, connector = drive
    connector.put("f1", "policy.txt", POLICY_TEXT.encode())
    sync(client)
    for p in get_settings().downloads_dir.iterdir():
        p.unlink()  # e.g. a new container whose disk was empty
    result = client.post("/api/v1/reindex").json()
    assert result["status"] == "partial" and result["failed"][0]["doc_id"] == "f1"
    assert [f["id"] for f in sync(client)["new_files"]] == ["f1"]
    assert client.get("/api/v1/documents/f1").json()["status"] == "indexed"


def test_concurrent_sync_rejected(drive):
    client, services, _ = drive
    services.sync_lock.acquire()
    try:
        assert client.post("/api/v1/sync-drive").status_code == 409
    finally:
        services.sync_lock.release()


# ── Connector unit tests ────────────────────────────────────

def test_headless_auth_without_token_fails_clearly(env):
    connector = GoogleDriveConnector(interactive=False)
    with pytest.raises(DriveAuthError) as exc:
        connector.authenticate()
    assert "python -m connectors.gdrive auth" in str(exc.value)


def test_sync_without_credentials_returns_400(make_client):
    client, _ = make_client()
    r = client.post("/api/v1/sync-drive")
    assert r.status_code == 400
    assert "OAuth token" in r.json()["detail"]


def test_invalid_folder_id_rejected(env):
    connector = GoogleDriveConnector(service=object())
    with pytest.raises(ValueError):
        connector.list_files(folder_id="abc' or name contains '")


def test_oversized_drive_file_rejected_before_download(env):
    env.setenv("DRIVE_MAX_FILE_MB", "1")
    get_settings.cache_clear()
    connector = GoogleDriveConnector(service=object())
    meta = {"id": "x", "name": "big.pdf", "mimeType": "application/pdf", "size": str(5 * 1024 * 1024)}
    with pytest.raises(DriveFileTooLarge):
        connector.download_file(meta)


def test_sync_run_directly(env, fake_embedder):
    from api.dependencies import Services

    services = Services(embedder=fake_embedder)
    connector = FakeDriveConnector()
    connector.put("f1", "policy.txt", POLICY_TEXT.encode())
    result = run_drive_sync(connector, services.pipeline)
    assert [f["id"] for f in result["new_files"]] == ["f1"]
    assert connector.state["f1"]["indexed"] is True
