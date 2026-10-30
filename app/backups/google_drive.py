from __future__ import annotations

import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveUnavailable(RuntimeError):
    """Raised when the Google Drive dependencies/configuration are unavailable."""


class GoogleDriveProvider:
    """Google Drive provider using OAuth for a desktop application.

    The provider is intentionally isolated from the rest of the application. A
    future cloud provider can implement the same small surface without touching
    the backup manager or settings UI.
    """

    def __init__(self, *, credentials_path: Path, token_path: Path) -> None:
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self._service = None

    @property
    def configured(self) -> bool:
        return self.credentials_path.exists()

    def authenticate(self, *, force_reauth: bool = False) -> dict[str, str]:
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GoogleDriveUnavailable(
                "Instala las dependencias de Google Drive ejecutando: "
                "python -m pip install -r requirements.txt"
            ) from exc
        if not self.credentials_path.exists():
            raise GoogleDriveUnavailable(
                "Selecciona primero el archivo de credenciales OAuth de tu proyecto de Google Cloud."
            )

        credentials = None
        if self.token_path.exists() and not force_reauth:
            try:
                credentials = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except (ValueError, json.JSONDecodeError, OSError):
                credentials = None

        if credentials and credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request
            credentials.refresh(Request())
        elif not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
            credentials = flow.run_local_server(port=0, open_browser=True)

        self.token_path.write_text(credentials.to_json(), encoding="utf-8")
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        about = self._service.about().get(fields="user(emailAddress,displayName)").execute()
        user = about.get("user", {})
        return {
            "email": str(user.get("emailAddress", "")),
            "display_name": str(user.get("displayName", "")),
        }

    def disconnect(self) -> None:
        self._service = None
        self.token_path.unlink(missing_ok=True)

    def _client(self):
        if self._service is not None:
            return self._service
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GoogleDriveUnavailable(
                "Instala las dependencias de Google Drive ejecutando: "
                "python -m pip install -r requirements.txt"
            ) from exc
        if not self.token_path.exists():
            raise GoogleDriveUnavailable("No hay una cuenta de Google Drive conectada.")
        credentials = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        if credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request
            credentials.refresh(Request())
            self.token_path.write_text(credentials.to_json(), encoding="utf-8")
        if not credentials.valid:
            raise GoogleDriveUnavailable("La sesión de Google Drive expiró. Conecta nuevamente la cuenta.")
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return self._service

    def ensure_folder(self, folder_name: str, existing_id: str = "") -> dict[str, str]:
        service = self._client()
        if existing_id:
            try:
                folder = service.files().get(fileId=existing_id, fields="id,name,webViewLink,mimeType").execute()
                if folder.get("mimeType") == "application/vnd.google-apps.folder":
                    return {"id": folder["id"], "name": folder["name"], "web_url": folder.get("webViewLink", "")}
            except Exception:
                pass
        escaped = folder_name.replace("'", "\\'")
        query = (
            "trashed = false and mimeType = 'application/vnd.google-apps.folder' "
            f"and name = '{escaped}'"
        )
        result = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id,name,webViewLink)",
            pageSize=10,
        ).execute()
        files = result.get("files", [])
        if files:
            folder = files[0]
            return {"id": folder["id"], "name": folder["name"], "web_url": folder.get("webViewLink", "")}

        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = service.files().create(
            body=metadata,
            fields="id,name,webViewLink",
        ).execute()
        return {"id": folder["id"], "name": folder["name"], "web_url": folder.get("webViewLink", "")}

    def share_folder_with_email(self, folder_id: str, email: str) -> None:
        if not email.strip():
            return
        service = self._client()
        existing = service.permissions().list(
            fileId=folder_id,
            fields="permissions(id,emailAddress,type,role)",
        ).execute().get("permissions", [])
        normalized = email.strip().lower()
        if any(str(p.get("emailAddress", "")).lower() == normalized for p in existing):
            return
        service.permissions().create(
            fileId=folder_id,
            sendNotificationEmail=True,
            body={"type": "user", "role": "reader", "emailAddress": email.strip()},
            fields="id,emailAddress",
        ).execute()

    def upload_backup(self, local_path: Path, folder_id: str) -> dict[str, str | int | bool]:
        service = self._client()
        try:
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise GoogleDriveUnavailable(
                "Instala las dependencias de Google Drive ejecutando: "
                "python -m pip install -r requirements.txt"
            ) from exc

        mime_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
        metadata = {"name": local_path.name, "parents": [folder_id]}
        media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)
        uploaded = service.files().create(
            body=metadata,
            media_body=media,
            fields="id,name,size,md5Checksum,createdTime,webViewLink",
        ).execute()
        verification = self.verify_backup(uploaded["id"], local_path)
        return {
            "id": str(uploaded["id"]),
            "name": str(uploaded.get("name", local_path.name)),
            "size": int(uploaded.get("size", 0)),
            "web_url": str(uploaded.get("webViewLink", "")),
            "verified": verification["verified"],
            "remote_md5": verification["remote_md5"],
            "local_md5": verification["local_md5"],
        }

    def verify_backup(self, file_id: str, local_path: Path) -> dict[str, Any]:
        service = self._client()
        metadata = service.files().get(fileId=file_id, fields="id,size,md5Checksum,name").execute()
        local_size = local_path.stat().st_size
        local_md5 = _md5(local_path)
        remote_size = int(metadata.get("size", -1))
        remote_md5 = str(metadata.get("md5Checksum", ""))
        verified = remote_size == local_size and (not remote_md5 or remote_md5 == local_md5)
        return {
            "verified": verified,
            "remote_size": remote_size,
            "local_size": local_size,
            "remote_md5": remote_md5,
            "local_md5": local_md5,
        }

    def list_backups(self, folder_id: str, limit: int = 100) -> list[dict[str, Any]]:
        service = self._client()
        query = f"'{folder_id}' in parents and trashed = false and name contains 'Tecnocity_Admin_Backup_'"
        result = service.files().list(
            q=query,
            spaces="drive",
            orderBy="createdTime desc",
            pageSize=min(max(limit, 1), 100),
            fields="files(id,name,size,createdTime,md5Checksum,webViewLink)",
        ).execute()
        return list(result.get("files", []))

    def download_backup(self, file_id: str, destination: Path) -> Path:
        service = self._client()
        try:
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError as exc:
            raise GoogleDriveUnavailable(
                "Instala las dependencias de Google Drive ejecutando: "
                "python -m pip install -r requirements.txt"
            ) from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as handle:
            request = service.files().get_media(fileId=file_id)
            downloader = MediaIoBaseDownload(handle, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return destination


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
