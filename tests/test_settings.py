from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from app.config import AppSettings


def test_settings_create_required_directories(tmp_path, monkeypatch):
    monkeypatch.setenv("TECNOCITY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TECNOCITY_LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("TECNOCITY_ASSETS_DIR", str(tmp_path / "assets"))

    settings = AppSettings.load()

    assert settings.data_dir.is_dir()
    assert settings.logs_dir.is_dir()
    assert settings.assets_dir.is_dir()
    assert settings.database_url.startswith("sqlite:///")
    assert settings.version == "1.10.0"


def test_settings_exposes_backup_and_google_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("TECNOCITY_DATA_DIR", str(tmp_path / "data"))
    settings = AppSettings.load()
    assert settings.database_path.name == "tecnocity_admin.db"
    assert settings.backups_dir.is_dir()
    assert settings.user_settings_path.name == "settings.json"
    assert settings.google_credentials_path.name == "client_secret.json"
    assert settings.google_token_path.name == "token.json"
    assert settings.backup_history_path.name == "backup_history.json"


def test_application_version_matches_release_metadata():
    settings_source = (ROOT / "app" / "config" / "settings.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version="1.10.0"' in settings_source
    assert 'version = "1.10.0"' in pyproject


def test_frozen_application_stores_user_data_outside_the_bundle(tmp_path, monkeypatch):
    import app.config.settings as settings_module

    monkeypatch.setattr(settings_module.sys, "frozen", True, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "UserData"))
    monkeypatch.delenv("TECNOCITY_DATA_DIR", raising=False)
    monkeypatch.delenv("TECNOCITY_LOGS_DIR", raising=False)

    settings = AppSettings.load()

    expected_root = tmp_path / "UserData" / "Tecnocity Admin"
    assert settings.data_dir == expected_root / "data"
    assert settings.logs_dir == expected_root / "logs"
    assert settings.database_path.parent == expected_root / "data"
    assert settings.assets_dir == settings.project_root / "assets"
    assert settings.data_dir.is_dir()
    assert settings.logs_dir.is_dir()
