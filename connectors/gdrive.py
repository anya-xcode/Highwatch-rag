"""
Google Drive Connector
Handles OAuth2 authentication and document fetching from Google Drive.
Supports PDFs, Google Docs, and plain text files.
"""

import io
import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config.settings import get_settings

logger = structlog.get_logger(__name__)

# Scopes required for reading Google Drive files
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
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
        "extension": ".docx",
        "export": None,
    },
}


class GoogleDriveConnector:
    """Connector for fetching documents from Google Drive."""

    def __init__(self):
        self.settings = get_settings()
        self.service = None
        self._sync_state_path = Path(self.settings.storage_dir) / "sync_state.json"
        self._download_dir = Path(self.settings.storage_dir) / "downloads"
        self._download_dir.mkdir(parents=True, exist_ok=True)

    def authenticate(self) -> None:
        """Authenticate with Google Drive using OAuth2."""
        creds = None
        token_path = self.settings.google_token_path
        credentials_path = self.settings.google_credentials_path

        # Load existing token
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logger.info("Loaded existing OAuth token")

        # Refresh or create new token
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired token")
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f"Google credentials file not found at '{credentials_path}'. "
                        "Download it from Google Cloud Console → APIs & Services → Credentials."
                    )
                logger.info("Starting OAuth2 flow")
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the token for future use
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())
            logger.info("Saved OAuth token", path=token_path)

        self.service = build("drive", "v3", credentials=creds)
        logger.info("Google Drive service initialized")

    def _ensure_authenticated(self) -> None:
        """Ensure the connector is authenticated."""
        if self.service is None:
            self.authenticate()

    def _load_sync_state(self) -> dict:
        """Load the sync state to track previously synced files."""
        if self._sync_state_path.exists():
            with open(self._sync_state_path, "r") as f:
                return json.load(f)
        return {}

    def _save_sync_state(self, state: dict) -> None:
        """Save the sync state."""
        with open(self._sync_state_path, "w") as f:
            json.dump(state, f, indent=2, default=str)

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of a file for change detection."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def list_files(
        self, folder_id: Optional[str] = None, page_size: int = 100
    ) -> list[dict]:
        """
        List supported files in Google Drive.
        
        Args:
            folder_id: Optional folder ID to scope the search.
            page_size: Number of files per page.
            
        Returns:
            List of file metadata dicts.
        """
        self._ensure_authenticated()

        # Build MIME type query
        mime_queries = " or ".join(
            f"mimeType='{mime}'" for mime in SUPPORTED_MIME_TYPES.keys()
        )
        query = f"({mime_queries}) and trashed=false"

        if folder_id:
            query = f"'{folder_id}' in parents and {query}"

        files = []
        page_token = None

        while True:
            response = (
                self.service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, md5Checksum)",
                    pageToken=page_token,
                    pageSize=page_size,
                )
                .execute()
            )

            files.extend(response.get("files", []))
            page_token = response.get("nextPageToken")

            if not page_token:
                break

        logger.info("Listed Google Drive files", count=len(files))
        return files

    def download_file(self, file_metadata: dict) -> Optional[Path]:
        """
        Download a file from Google Drive.
        
        Args:
            file_metadata: File metadata dict from list_files().
            
        Returns:
            Path to the downloaded file, or None if unsupported.
        """
        self._ensure_authenticated()

        file_id = file_metadata["id"]
        mime_type = file_metadata["mimeType"]
        file_name = file_metadata["name"]

        if mime_type not in SUPPORTED_MIME_TYPES:
            logger.warning("Unsupported MIME type", mime_type=mime_type, file=file_name)
            return None

        type_info = SUPPORTED_MIME_TYPES[mime_type]
        
        # Ensure file has proper extension
        ext = type_info["extension"]
        if not file_name.lower().endswith(ext):
            file_name = f"{file_name}{ext}"

        output_path = self._download_dir / f"{file_id}_{file_name}"

        try:
            if type_info["export"]:
                # Google Docs need to be exported
                request = self.service.files().export_media(
                    fileId=file_id, mimeType=type_info["export"]
                )
            else:
                # Regular files can be downloaded directly
                request = self.service.files().get_media(fileId=file_id)

            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            
            done = False
            while not done:
                _, done = downloader.next_chunk()

            with open(output_path, "wb") as f:
                f.write(buffer.getvalue())

            logger.info(
                "Downloaded file",
                file=file_name,
                size=output_path.stat().st_size,
            )
            return output_path

        except Exception as e:
            logger.error("Failed to download file", file=file_name, error=str(e))
            raise

    def sync(self, folder_ids: Optional[list[str]] = None) -> dict:
        """
        Sync files from Google Drive with incremental change detection.
        
        Args:
            folder_ids: Optional list of folder IDs. Uses config if not provided.
            
        Returns:
            Sync result with lists of new, updated, and unchanged files.
        """
        self._ensure_authenticated()
        
        if folder_ids is None:
            folder_ids = self.settings.folder_ids

        sync_state = self._load_sync_state()
        result = {
            "new_files": [],
            "updated_files": [],
            "unchanged_files": [],
            "errors": [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        # List files from all specified folders (or root if none specified)
        all_files = []
        if folder_ids:
            for folder_id in folder_ids:
                all_files.extend(self.list_files(folder_id=folder_id))
        else:
            all_files = self.list_files()

        for file_meta in all_files:
            file_id = file_meta["id"]
            modified_time = file_meta.get("modifiedTime", "")
            
            try:
                prev_state = sync_state.get(file_id, {})
                prev_modified = prev_state.get("modifiedTime", "")

                if prev_modified == modified_time and prev_state.get("downloaded"):
                    # File hasn't changed
                    result["unchanged_files"].append({
                        "id": file_id,
                        "name": file_meta["name"],
                    })
                    continue

                # Download new or updated file
                file_path = self.download_file(file_meta)
                if file_path is None:
                    continue

                file_hash = self._compute_file_hash(file_path)

                # Check if content actually changed
                if prev_state.get("hash") == file_hash:
                    result["unchanged_files"].append({
                        "id": file_id,
                        "name": file_meta["name"],
                    })
                else:
                    category = "new_files" if not prev_state else "updated_files"
                    result[category].append({
                        "id": file_id,
                        "name": file_meta["name"],
                        "path": str(file_path),
                        "mime_type": file_meta["mimeType"],
                    })

                # Update sync state
                sync_state[file_id] = {
                    "name": file_meta["name"],
                    "modifiedTime": modified_time,
                    "hash": file_hash,
                    "path": str(file_path),
                    "downloaded": True,
                    "synced_at": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                logger.error("Sync error for file", file=file_meta["name"], error=str(e))
                result["errors"].append({
                    "id": file_id,
                    "name": file_meta["name"],
                    "error": str(e),
                })

        self._save_sync_state(sync_state)
        
        logger.info(
            "Sync completed",
            new=len(result["new_files"]),
            updated=len(result["updated_files"]),
            unchanged=len(result["unchanged_files"]),
            errors=len(result["errors"]),
        )
        return result
