from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

CURRENT_SCHEMA_VERSION = 1

DEFAULT_USER_SETTINGS: dict[str, dict[str, Any]] = {
    "general": {
        "business_name": "Tecnocity",
        "currency": "COP",
    },
    "appearance": {
        "theme": "light",
    },
    "backup": {
        "enabled": True,
        "google_enabled": True,
        "google_connected": False,
        "google_account_email": "",
        "google_destination_email": "",
        "google_folder_name": "Tecnocity Admin - Backups",
        "google_folder_id": "",
        "schedule_enabled": False,
        "schedule_time": "23:00",
        "backup_on_startup": False,
        "keep_local_copies": 10,
        "windows_task_name": "Tecnocity Admin - Backup Automático",
    },
}


class SettingsStore:
    """Persistent user settings with deep-merge defaults and atomic writes."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def section(self, section: str) -> dict[str, Any]:
        value = self._data.get(section, {})
        return value if isinstance(value, dict) else {}

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self.section(section).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        self._data.setdefault(section, {})[key] = value

    def update_section(self, section: str, values: dict[str, Any]) -> None:
        self._data.setdefault(section, {}).update(values)

    def save(self) -> None:
        payload = {"schema_version": CURRENT_SCHEMA_VERSION, **self._data}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_name = None
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as temp:
                temp_name = temp.name
                json.dump(payload, temp, ensure_ascii=False, indent=2)
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_name, self.path)
            temp_name = None
        finally:
            if temp_name:
                Path(temp_name).unlink(missing_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return copy.deepcopy(DEFAULT_USER_SETTINGS)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            user_data = {k: v for k, v in raw.items() if k != "schema_version"} if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError):
            user_data = {}
        return _deep_merge(copy.deepcopy(DEFAULT_USER_SETTINGS), user_data)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base
