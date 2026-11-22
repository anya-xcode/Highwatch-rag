"""
Persistence backends.

The application always works on files in STORAGE_DIR. A backend optionally
mirrors those files somewhere durable:

- LocalBackend (default, $0): no-op. Files persist as long as the disk does
  (your machine, or a Docker volume).
- GCSBackend (opt-in): mirrors STORAGE_DIR to a *private* Google Cloud Storage
  bucket so the index survives Cloud Run restarts. Requires a GCP project with
  a billing account; see README "Cost and billing warnings" before enabling.
"""

from pathlib import Path
from typing import Iterable, Optional

import structlog

logger = structlog.get_logger(__name__)


class PersistenceBackend:
    """Base class / local no-op backend."""

    name = "local"

    def restore(self) -> int:
        """Copy remote state into STORAGE_DIR. Returns number of files restored."""
        return 0

    def persist(self, *paths: str | Path) -> None:
        """Upload the given local files (no-op locally)."""

    def remove(self, *paths: str | Path) -> None:
        """Delete the remote copies of the given local files (no-op locally)."""

    def describe(self) -> dict:
        return {"backend": self.name}


class LocalBackend(PersistenceBackend):
    name = "local"


class GCSBackend(PersistenceBackend):
    """Mirror STORAGE_DIR into gs://<bucket>/<prefix>/..."""

    name = "gcs"

    def __init__(self, bucket: str, prefix: str, storage_dir: str | Path, client=None):
        if not bucket:
            raise ValueError("GCS_BUCKET must be set when STORAGE_BACKEND=gcs")
        if client is None:
            # Imported lazily so the default local setup never needs GCP libraries
            # or credentials.
            from google.cloud import storage

            client = storage.Client()
        self._bucket_name = bucket
        self._bucket = client.bucket(bucket)
        self._prefix = prefix.strip("/")
        self._root = Path(storage_dir).resolve()
        self.failures = 0

    def _blob_name(self, path: str | Path) -> Optional[str]:
        try:
            rel = Path(path).resolve().relative_to(self._root).as_posix()
        except ValueError:
            logger.warning("Path is outside STORAGE_DIR; not mirrored to GCS", path=str(path))
            return None
        return f"{self._prefix}/{rel}" if self._prefix else rel

    def restore(self) -> int:
        count = 0
        prefix = f"{self._prefix}/" if self._prefix else ""
        for blob in self._bucket.list_blobs(prefix=prefix):
            rel = blob.name[len(prefix):]
            if not rel or rel.endswith("/"):
                continue
            dest = (self._root / rel).resolve()
            if self._root not in dest.parents:
                logger.warning("Skipping unsafe object name", name=blob.name)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(dest))
            count += 1
        logger.info("Restored storage from GCS", bucket=self._bucket_name, files=count)
        return count

    def persist(self, *paths: str | Path) -> None:
        for path in _existing(paths):
            name = self._blob_name(path)
            if not name:
                continue
            try:
                self._bucket.blob(name).upload_from_filename(str(path))
            except Exception as e:  # noqa: BLE001
                self.failures += 1
                logger.error("GCS upload failed", object=name, error=str(e))

    def remove(self, *paths: str | Path) -> None:
        for path in paths:
            name = self._blob_name(path)
            if not name:
                continue
            try:
                self._bucket.blob(name).delete()
            except Exception as e:  # noqa: BLE001 - NotFound is fine
                logger.debug("GCS delete skipped", object=name, error=str(e))

    def describe(self) -> dict:
        return {
            "backend": self.name,
            "bucket": self._bucket_name,
            "prefix": self._prefix,
            "upload_failures": self.failures,
        }


def _existing(paths: Iterable[str | Path]) -> list[Path]:
    return [Path(p) for p in paths if p and Path(p).exists()]


_backend: Optional[PersistenceBackend] = None


def get_persistence() -> PersistenceBackend:
    """Return the configured backend (singleton)."""
    global _backend
    if _backend is None:
        from config.settings import get_settings

        settings = get_settings()
        if settings.storage_backend == "gcs":
            _backend = GCSBackend(settings.gcs_bucket, settings.gcs_prefix, settings.storage_dir)
        else:
            _backend = LocalBackend()
    return _backend


def set_persistence(backend: Optional[PersistenceBackend]) -> None:
    """Override the backend (used by tests)."""
    global _backend
    _backend = backend
