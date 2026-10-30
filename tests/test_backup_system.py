from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.backups import BackupManager, BackupStatus, WindowsBackupScheduler
from app.config import AppSettings, SettingsStore


def _make_sqlite(path: Path, value: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("create table if not exists sample (value text not null)")
        conn.execute("delete from sample")
        conn.execute("insert into sample(value) values (?)", (value,))
        conn.commit()


def _manager(tmp_path: Path, db_path: Path | None = None) -> BackupManager:
    db = db_path or (tmp_path / "tecnocity_admin.db")
    store = SettingsStore(tmp_path / "settings.json")
    return BackupManager(
        database_path=db,
        backups_dir=tmp_path / "backups",
        credentials_path=tmp_path / "google" / "client_secret.json",
        token_path=tmp_path / "google" / "token.json",
        history_path=tmp_path / "backups" / "backup_history.json",
        settings_store=store,
    )


def test_settings_store_defaults_and_atomic_persistence(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    assert store.get("backup", "google_enabled") is True
    store.set("backup", "google_destination_email", "destino@example.com")
    store.save()
    reloaded = SettingsStore(path)
    assert reloaded.get("backup", "google_destination_email") == "destino@example.com"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1


def test_local_backup_creates_valid_snapshot_and_history(tmp_path):
    db = tmp_path / "tecnocity_admin.db"
    _make_sqlite(db, "original")
    manager = _manager(tmp_path, db)
    manager.settings_store.set("backup", "google_enabled", False)
    manager.settings_store.save()
    result = manager.backup_now(reason="test")
    assert result.status is BackupStatus.SUCCESS
    assert result.local_path is not None and result.local_path.exists()
    with sqlite3.connect(result.local_path) as conn:
        assert conn.execute("select value from sample").fetchone()[0] == "original"
        assert conn.execute("pragma integrity_check").fetchone()[0] == "ok"
    entries = manager.history.list()
    assert entries[0]["verified"] is True
    assert entries[0]["reason"] == "test"


def test_restore_creates_safety_copy_and_restores_database(tmp_path):
    db = tmp_path / "tecnocity_admin.db"
    _make_sqlite(db, "before")
    manager = _manager(tmp_path, db)
    source = manager.create_local_snapshot()
    _make_sqlite(db, "after")
    safety = manager.restore_local(source)
    with sqlite3.connect(db) as conn:
        assert conn.execute("select value from sample").fetchone()[0] == "before"
        assert conn.execute("pragma integrity_check").fetchone()[0] == "ok"
    assert safety.exists()


def test_local_backup_retention(tmp_path):
    db = tmp_path / "tecnocity_admin.db"
    _make_sqlite(db, "x")
    manager = _manager(tmp_path, db)
    manager.settings_store.set("backup", "google_enabled", False)
    manager.settings_store.set("backup", "keep_local_copies", 2)
    manager.settings_store.save()
    # Force distinct filenames so retention can be evaluated without waiting a second.
    for index in range(4):
        path = manager.backups_dir / f"manual_{index}.db"
        _make_sqlite(path, str(index))
    manager._apply_retention()
    assert len(manager.local_backups(limit=100)) == 2


def test_scheduler_rejects_invalid_time(tmp_path):
    scheduler = WindowsBackupScheduler(project_root=tmp_path, task_name="Tecnocity Test Backup")
    ok, _ = scheduler.install("25:99")
    assert ok is False


def test_scheduler_reports_support_status(tmp_path):
    scheduler = WindowsBackupScheduler(project_root=tmp_path, task_name="Tecnocity Test Backup")
    status = scheduler.status()
    assert status["supported"] == (scheduler.supported)


def test_google_backup_orchestration_with_provider_fake(tmp_path):
    db = tmp_path / "tecnocity_admin.db"
    _make_sqlite(db, "cloud")
    manager = _manager(tmp_path, db)
    manager.settings_store.update_section("backup", {
        "google_enabled": True,
        "google_connected": True,
        "google_account_email": "owner@example.com",
        "google_destination_email": "dest@example.com",
        "google_folder_name": "Tecnocity Admin - Backups",
    })
    manager.settings_store.save()

    class FakeGoogle:
        token_path = tmp_path / "google" / "token.json"

        def __init__(self):
            self.calls = []

        def ensure_folder(self, folder_name, existing_id=""):
            self.calls.append(("folder", folder_name, existing_id))
            return {"id": "folder-1", "name": folder_name, "web_url": "https://drive.google.com/"}

        def share_folder_with_email(self, folder_id, email):
            self.calls.append(("share", folder_id, email))

        def upload_backup(self, local_path, folder_id):
            self.calls.append(("upload", local_path.name, folder_id))
            return {"id": "file-1", "name": local_path.name, "size": local_path.stat().st_size, "web_url": "https://drive.google.com/file-1", "verified": True}

    fake = FakeGoogle()
    fake.token_path.parent.mkdir(parents=True, exist_ok=True)
    fake.token_path.write_text("token", encoding="utf-8")
    manager.google = fake
    result = manager.backup_now(reason="test-google")
    assert result.status is BackupStatus.SUCCESS
    assert result.verified is True
    assert [call[0] for call in fake.calls] == ["folder", "share", "upload"]
    assert manager.settings_store.get("backup", "google_folder_id") == "folder-1"


def test_scheduled_cli_is_parser_backed():
    from app.main import build_parser
    assert build_parser().parse_args(["--backup-now"]).backup_now is True
