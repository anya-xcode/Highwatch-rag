"""
Google Drive Connector
Handles OAuth2 authentication and document fetching from Google Drive.
Supports PDFs, Google Docs, DOCX and plain text files.

The Drive API has no charge for standard use. Keep the Google Cloud project
that owns the OAuth client WITHOUT a billing account if you want to be sure it
can never be billed (Google has announced charges for exceeding quotas).

Sync is two-phase: `plan_sync()` downloads new/changed files and reports
removals without touching the saved state; the caller indexes the files and
then calls `commit()` / `forget()` so a file that failed to index is retried
on the next sync.

Get a token on your own machine (opens a browser once):
    python -m connectors.gdrive auth
"""

import os
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from config.settings import Settings, get_settings
from persistence.backends import PersistenceBackend, get_persistence
from persistence.files import atomic_write_json, read_json

logger = structlog.get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

# Supported MIME types and their export formats
SUPPORTED_MIME_TYPES = {
    "application/pdf": {"extension": ".pdf", "export": None},
    "application/vnd.google-apps.document": {
        "extension": ".docx",
        "export": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    "text/plain": {"extension": ".txt", "export": None},
    "text/markdown": {"extension": ".md", "export": None},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
        "extension": ".docx",
        "export": None,
    },
}

_FOLDER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{5,200}$")


class DriveAuthError(RuntimeError):
    """Google Drive authentication is missing, expired or impossible here."""


class DriveFileTooLarge(RuntimeError):
    """A Drive file exceeds DRIVE_MAX_FILE_MB."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class GoogleDriveConnector:
    """Connector for fetching documents from Google Drive."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        service=None,
        persistence: Optional[PersistenceBackend] = None,
        interactive: Optional[bool] = None,
    ):
        self.settings = settings or get_settings()
        self.service = service
        self._persistence = persistence or get_persistence()
        self.interactive = self.settings.google_oauth_interactive if interactive is None else interactive
        self._sync_state_path = self.settings.sync_state_path
        self._download_dir = self.settings.downloads_dir
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._state: Optional[dict] = None

    # ── Auth ───────────────────────────────────────────────

    def is_configured(self) -> bool:
        return os.path.exists(self.settings.google_token_path) or os.path.exists(
            self.settings.google_credentials_path
        )

    def authenticate(self) -> None:
        """Authenticate with Google Drive using OAuth2."""
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        token_path = self.settings.google_token_path
        credentials_path = self.settings.google_credentials_path
        creds = None

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            refreshed = False
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired Google token")
                    creds.refresh(Request())
                    refreshed = True
                except RefreshError as e:
                    logger.warning("Google token refresh failed", error=str(e))
                    if not self.interactive:
                        raise DriveAuthError(
                            "The Google OAuth token has expired or was revoked. OAuth apps in "
                            "'Testing' status issue tokens that expire after 7 days. Run "
                            "'python -m connectors.gdrive auth' on your own machine and redeploy "
                            "the new token.json (or GOOGLE_TOKEN_JSON)."
                        ) from e

            if not refreshed:
                if not self.interactive:
                    raise DriveAuthError(
                        "No valid Google OAuth token and interactive login is disabled "
                        "(GOOGLE_OAUTH_INTERACTIVE=false). Run 'python -m connectors.gdrive auth' "
                        "locally and provide token.json (or GOOGLE_TOKEN_JSON)."
                    )
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f"Google credentials file not found at '{credentials_path}'. "
                        "Create an OAuth client (Desktop app) in Google Cloud Console → "
                        "APIs & Services → Credentials and download it."
                    )
                from google_auth_oauthlib.flow import InstalledAppFlow

                logger.info("Starting OAuth2 browser flow")
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            Path(token_path).parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
            logger.info("Saved OAuth token", path=token_path)

        self.service = build("drive", "v3", credentials=creds, cache_discovery=False)
        logger.info("Google Drive service initialized")

    def _ensure_authenticated(self) -> None:
        if self.service is None:
            self.authenticate()

    # ── Sync state ─────────────────────────────────────────

    @property
    def state(self) -> dict:
        if self._state is None:
            try:
                self._state = read_json(self._sync_state_path, default={})
            except Exception as e:  # noqa: BLE001
                logger.error("Sync state unreadable; starting fresh", error=str(e))
                self._state = {}
        return self._state

    def commit(self, file_id: str, entry: dict) -> None:
        """Record a file as successfully indexed (and mirror the download)."""
        self.state[file_id] = {**entry, "indexed": True, "synced_at": _utc_now()}
        self._save_state()
        if entry.get("path"):
            self._persistence.persist(entry["path"])

    def forget(self, file_id: str) -> None:
        """Remove a file from the sync state (it will be treated as new)."""
        entry = self.state.pop(file_id, None)
        if entry is not None:
            self._save_state()
            if entry.get("path"):
                self._persistence.remove(entry["path"])

    def reset_state(self) -> None:
        self._state = {}
        self._save_state()

    def _save_state(self) -> None:
        atomic_write_json(self._sync_state_path, self.state)
        self._persistence.persist(self._sync_state_path)

    # ── Drive API ──────────────────────────────────────────

    @staticmethod
    def scope_key(folder_ids: Optional[list[str]]) -> str:
        return ",".join(sorted(folder_ids)) if folder_ids else "root"

    def list_files(self, folder_id: Optional[str] = None, page_size: int = 100) -> list[dict]:
        """List supported (non-trashed) files, optionally directly inside one folder."""
        self._ensure_authenticated()

        mime_queries = " or ".join(f"mimeType='{mime}'" for mime in SUPPORTED_MIME_TYPES)
        query = f"({mime_queries}) and trashed=false"
        if folder_id:
            if not _FOLDER_ID_RE.match(folder_id):
                raise ValueError(f"Invalid Google Drive folder ID: {folder_id!r}")
            query = f"'{folder_id}' in parents and {query}"

        files, page_token = [], None
        while True:
            response = (
                self.service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, md5Checksum, webViewLink)",
                    pageToken=page_token,
                    pageSize=page_size,
                )
                .execute()
            )
            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        logger.info("Listed Google Drive files", count=len(files), folder=folder_id or "all")
        return files

    def download_file(self, file_metadata: dict) -> Optional[Path]:
        """Download (or export) a file into STORAGE_DIR/downloads."""
        from googleapiclient.http import MediaIoBaseDownload

        self._ensure_authenticated()
        file_id = file_metadata["id"]
        mime_type = file_metadata["mimeType"]
        file_name = file_metadata["name"]

        type_info = SUPPORTED_MIME_TYPES.get(mime_type)
        if type_info is None:
            logger.warning("Unsupported MIME type", mime_type=mime_type, file=file_name)
            return None

        size = int(file_metadata.get("size") or 0)
        if size > self.settings.drive_max_file_bytes:
            raise DriveFileTooLarge(
                f"File is {size / 1_048_576:.1f} MB; DRIVE_MAX_FILE_MB is {self.settings.drive_max_file_mb}"
            )

        ext = type_info["extension"]
        safe_name = re.sub(r"[^\w.\- ()]+", "_", file_name).strip(" .") or "document"
        if not safe_name.lower().endswith(ext):
            safe_name = f"{safe_name}{ext}"
        output_path = self._download_dir / f"{file_id}_{safe_name}"
        tmp_path = output_path.with_name(output_path.name + ".part")

        if type_info["export"]:
            request = self.service.files().export_media(fileId=file_id, mimeType=type_info["export"])
        else:
            request = self.service.files().get_media(fileId=file_id)

        try:
            with open(tmp_path, "wb") as fh:  # stream to disk, not memory
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                    if fh.tell() > self.settings.drive_max_file_bytes:
                        raise DriveFileTooLarge(
                            f"Download exceeded DRIVE_MAX_FILE_MB ({self.settings.drive_max_file_mb} MB)"
                        )
            os.replace(tmp_path, output_path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        logger.info("Downloaded file", file=file_name, size=output_path.stat().st_size)
        return output_path

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def plan_sync(self, folder_ids: Optional[list[str]] = None) -> dict:
        """
        Download new/changed files and detect removed ones. Does NOT save state.

        Returns a dict with lists: new_files, updated_files, unchanged_files,
        removed_files, errors (plus scope and timestamp). Entries in new/updated
        carry an internal "state" dict to pass to commit() after indexing.
        """
        self._ensure_authenticated()
        if folder_ids is None:
            folder_ids = self.settings.folder_ids
        scope = self.scope_key(folder_ids)

        result = {
            "new_files": [],
            "updated_files": [],
            "unchanged_files": [],
            "removed_files": [],
            "errors": [],
            "scope": scope,
            "timestamp": _utc_now(),
        }

        listed: dict[str, dict] = {}
        for folder_id in folder_ids or [None]:
            for meta in self.list_files(folder_id=folder_id):
                listed[meta["id"]] = meta

        for file_id, meta in listed.items():
            prev = self.state.get(file_id, {})
            modified = meta.get("modifiedTime", "")
            base = {"id": file_id, "name": meta["name"]}
            try:
                if prev.get("indexed") and prev.get("modifiedTime") == modified:
                    result["unchanged_files"].append(base)
                    continue

                path = self.download_file(meta)
                if path is None:
                    continue
                file_hash = self.compute_file_hash(path)
                state = {
                    "name": meta["name"],
                    "modifiedTime": modified,
                    "hash": file_hash,
                    "path": str(path),
                    "scope": scope,
                }

                if prev.get("indexed") and prev.get("hash") == file_hash:
                    # Touched but identical content: just refresh the timestamp.
                    self.commit(file_id, {**prev, **state})
                    result["unchanged_files"].append(base)
                    continue

                category = "updated_files" if prev.get("indexed") else "new_files"
                result[category].append(
                    {
                        **base,
                        "path": str(path),
                        "mime_type": meta["mimeType"],
                        "url": meta.get("webViewLink"),
                        "size_bytes": path.stat().st_size,
                        "state": state,
                    }
                )
            except Exception as e:  # noqa: BLE001
                logger.error("Sync error for file", file=meta.get("name"), error=str(e))
                result["errors"].append({**base, "error": str(e)})

        for file_id, prev in list(self.state.items()):
            if file_id not in listed and prev.get("scope", scope) == scope:
                result["removed_files"].append({"id": file_id, "name": prev.get("name", ""), "path": prev.get("path")})

        logger.info(
            "Sync planned",
            new=len(result["new_files"]),
            updated=len(result["updated_files"]),
            unchanged=len(result["unchanged_files"]),
            removed=len(result["removed_files"]),
            errors=len(result["errors"]),
        )
        return result


def _cli() -> None:  # pragma: no cover - manual helper
    import sys

    if len(sys.argv) < 2 or sys.argv[1] != "auth":
        print("Usage: python -m connectors.gdrive auth")
        raise SystemExit(2)
    connector = GoogleDriveConnector(interactive=True)
    connector.authenticate()
    files = connector.list_files()
    print(f"Authenticated. Token saved to {connector.settings.google_token_path}.")
    print(f"Visible supported files: {len(files)}")


if __name__ == "__main__":  # pragma: no cover
    _cli()
