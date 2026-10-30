from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import sys

from app.utils.paths import project_root


@dataclass(frozen=True, slots=True)
class AppSettings:
    app_name: str
    version: str
    project_root: Path
    data_dir: Path
    logs_dir: Path
    assets_dir: Path
    database_url: str
    database_path: Path
    backups_dir: Path
    config_dir: Path
    user_settings_path: Path
    google_dir: Path
    google_credentials_path: Path
    google_token_path: Path
    backup_history_path: Path

    @classmethod
    def load(cls) -> "AppSettings":
        root = project_root()
        frozen = bool(getattr(sys, "frozen", False))
        if frozen:
            if os.name == "nt":
                user_data_root = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
            else:
                user_data_root = Path(os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
            user_data_root = user_data_root / "Tecnocity Admin"
        else:
            user_data_root = root

        data_dir = Path(os.getenv("TECNOCITY_DATA_DIR", str(user_data_root / "data")))
        logs_dir = Path(os.getenv("TECNOCITY_LOGS_DIR", str(user_data_root / "logs")))
        assets_dir = Path(os.getenv("TECNOCITY_ASSETS_DIR", str(root / "assets")))
        config_dir = data_dir / "config"
        backups_dir = data_dir / "backups"
        google_dir = config_dir / "google"
        for directory in (data_dir, logs_dir, assets_dir, config_dir, backups_dir, google_dir):
            directory.mkdir(parents=True, exist_ok=True)
        database_path = data_dir / "tecnocity_admin.db"
        return cls(
            app_name="Tecnocity Admin",
            version="1.10.0",
            project_root=root,
            data_dir=data_dir,
            logs_dir=logs_dir,
            assets_dir=assets_dir,
            database_url=f"sqlite:///{database_path}",
            database_path=database_path,
            backups_dir=backups_dir,
            config_dir=config_dir,
            user_settings_path=config_dir / "settings.json",
            google_dir=google_dir,
            google_credentials_path=google_dir / "client_secret.json",
            google_token_path=google_dir / "token.json",
            backup_history_path=backups_dir / "backup_history.json",
        )
