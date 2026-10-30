from __future__ import annotations

import logging
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from app.backups.google_drive import GoogleDriveProvider, GoogleDriveUnavailable
from app.backups.history import BackupHistory

logger = logging.getLogger(__name__)


class BackupStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(slots=True)
class BackupResult:
    status: BackupStatus
    created_at: datetime
    local_path: Path | None = None
    drive_file_id: str = ""
    drive_file_name: str = ""
    drive_url: str = ""
    verified: bool = False
    message: str = ""

    @property
    def success(self) -> bool:
        return self.status is BackupStatus.SUCCESS


class BackupManager:
    """Orchestrates local snapshots and pluggable remote backup providers."""

    def __init__(
        self,
        *,
        database_path: Path,
        backups_dir: Path,
        credentials_path: Path,
        token_path: Path,
        history_path: Path,
        settings_store,
        engine=None,
    ) -> None:
        self.database_path = Path(database_path)
        self.backups_dir = Path(backups_dir)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.settings_store = settings_store
        self.engine = engine
        self.history = BackupHistory(history_path)
        self.google = GoogleDriveProvider(credentials_path=credentials_path, token_path=token_path)

    def local_backups(self, limit: int = 50) -> list[Path]:
        files = [p for p in self.backups_dir.glob("*.db") if p.is_file()]
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

    def authenticate_google(self, *, force_reauth: bool = False) -> dict[str, str]:
        if force_reauth:
            self.google.disconnect()
            self.settings_store.update_section("backup", {"google_connected": False, "google_account_email": "", "google_folder_id": ""})
        identity = self.google.authenticate(force_reauth=force_reauth)
        self.settings_store.update_section("backup", {
            "google_connected": True,
            "google_account_email": identity.get("email", ""),
        })
        self.settings_store.save()
        return identity

    def disconnect_google(self) -> None:
        self.google.disconnect()
        self.settings_store.update_section("backup", {
            "google_connected": False,
            "google_account_email": "",
            "google_folder_id": "",
        })
        self.settings_store.save()

    def google_status(self) -> dict[str, Any]:
        section = self.settings_store.section("backup")
        return {
            "connected": bool(section.get("google_connected")) and self.google.token_path.exists(),
            "email": str(section.get("google_account_email", "")),
            "folder_id": str(section.get("google_folder_id", "")),
        }

    def backup_now(self, *, reason: str = "manual") -> BackupResult:
        started = datetime.now()
        local_path = self.create_local_snapshot()
        section = self.settings_store.section("backup")
        drive_enabled = bool(section.get("google_enabled", True))
        connected = self.google_status()["connected"]

        if not drive_enabled:
            result = BackupResult(
                status=BackupStatus.SUCCESS,
                created_at=started,
                local_path=local_path,
                verified=True,
                message="Copia local creada correctamente.",
            )
            self._record(result, reason=reason, destination="LOCAL")
            self._apply_retention()
            return result

        if not connected:
            result = BackupResult(
                status=BackupStatus.PARTIAL,
                created_at=started,
                local_path=local_path,
                verified=True,
                message="Copia local creada. Google Drive no está conectado.",
            )
            self._record(result, reason=reason, destination="LOCAL")
            self._apply_retention()
            return result

        try:
            folder_name = str(section.get("google_folder_name") or "Tecnocity Admin - Backups")
            folder = self.google.ensure_folder(folder_name, str(section.get("google_folder_id", "")))
            destination_email = str(section.get("google_destination_email", "")).strip()
            connected_email = str(section.get("google_account_email", "")).strip()
            if destination_email and destination_email.lower() != connected_email.lower():
                self.google.share_folder_with_email(folder["id"], destination_email)
            self.settings_store.update_section("backup", {"google_folder_id": folder["id"]})
            drive_file = self.google.upload_backup(local_path, folder["id"])
            verified = bool(drive_file.get("verified"))
            status = BackupStatus.SUCCESS if verified else BackupStatus.FAILED
            message = "Copia local y Google Drive verificadas correctamente." if verified else "La copia se subió, pero la verificación remota falló."
            result = BackupResult(
                status=status,
                created_at=started,
                local_path=local_path,
                drive_file_id=str(drive_file.get("id", "")),
                drive_file_name=str(drive_file.get("name", "")),
                drive_url=str(drive_file.get("web_url", "")),
                verified=verified,
                message=message,
            )
            self._record(result, reason=reason, destination="GOOGLE_DRIVE")
            self._apply_retention()
            self.settings_store.save()
            return result
        except Exception as exc:
            logger.exception("Google Drive backup failed")
            result = BackupResult(
                status=BackupStatus.PARTIAL,
                created_at=started,
                local_path=local_path,
                verified=True,
                message=f"Copia local creada, pero Google Drive falló: {exc}",
            )
            self._record(result, reason=reason, destination="LOCAL+GOOGLE_DRIVE")
            self._apply_retention()
            return result

    def create_local_snapshot(self) -> Path:
        if not self.database_path.exists():
            raise FileNotFoundError(f"No existe la base de datos: {self.database_path}")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        destination = self.backups_dir / f"Tecnocity_Admin_Backup_{timestamp}.db"
        source = sqlite3.connect(str(self.database_path))
        target = sqlite3.connect(str(destination))
        try:
            source.execute("PRAGMA wal_checkpoint(FULL)")
            source.backup(target)
            integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"La copia local no pasó integrity_check: {integrity}")
        finally:
            target.close()
            source.close()
        return destination

    def restore_local(self, backup_path: Path) -> Path:
        return self._restore_database(Path(backup_path))

    def restore_google(self, file_id: str) -> Path:
        temp = self.backups_dir / f".restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        self.google.download_backup(file_id, temp)
        try:
            return self._restore_database(temp)
        finally:
            temp.unlink(missing_ok=True)

    def _restore_database(self, backup_path: Path) -> Path:
        if not backup_path.exists():
            raise FileNotFoundError(f"No existe el respaldo: {backup_path}")
        integrity = sqlite3.connect(f"file:{backup_path.as_posix()}?mode=ro", uri=True)
        try:
            check = integrity.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok":
                raise RuntimeError(f"El respaldo está dañado: {check}")
        finally:
            integrity.close()

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        safety = self.backups_dir / f"PreRestore_{timestamp}.db"
        if self.engine is not None:
            self.engine.dispose()
        shutil.copy2(self.database_path, safety)
        staged = self.database_path.with_suffix(".restore.tmp")
        shutil.copy2(backup_path, staged)
        try:
            with sqlite3.connect(str(staged)) as staged_conn:
                staged_conn.execute("PRAGMA user_version").fetchone()
            staged.replace(self.database_path)
        except Exception:
            staged.unlink(missing_ok=True)
            raise
        return safety

    def list_remote_backups(self, limit: int = 100) -> list[dict[str, Any]]:
        section = self.settings_store.section("backup")
        folder_id = str(section.get("google_folder_id", ""))
        if not folder_id:
            return []
        return self.google.list_backups(folder_id, limit=limit)

    def _record(self, result: BackupResult, *, reason: str, destination: str) -> None:
        self.history.append({
            "created_at": result.created_at.isoformat(timespec="seconds"),
            "status": result.status.value,
            "reason": reason,
            "destination": destination,
            "local_path": str(result.local_path) if result.local_path else "",
            "drive_file_id": result.drive_file_id,
            "drive_file_name": result.drive_file_name,
            "verified": result.verified,
            "message": result.message,
        })

    def _apply_retention(self) -> None:
        try:
            keep = max(1, int(self.settings_store.section("backup").get("keep_local_copies", 10)))
        except (TypeError, ValueError):
            keep = 10
        for old in self.local_backups(limit=1000)[keep:]:
            old.unlink(missing_ok=True)
