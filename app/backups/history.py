from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


class BackupHistory:
    """Small, human-readable audit trail for backup executions.

    Backup history intentionally lives outside the operational SQLite database so
    the database can be copied/restored without recursively rewriting its own
    backup status during the backup operation.
    """

    def __init__(self, path: Path, max_entries: int = 100) -> None:
        self.path = Path(path)
        self.max_entries = max_entries
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self, limit: int | None = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            entries = payload.get("entries", [])
            if not isinstance(entries, list):
                return []
            result = [entry for entry in entries if isinstance(entry, dict)]
            return result[:limit] if limit else result
        except (OSError, json.JSONDecodeError):
            return []

    def append(self, entry: dict[str, Any]) -> None:
        entries = self.list(limit=None)
        entries.insert(0, dict(entry))
        entries = entries[: self.max_entries]
        payload = {
            "schema_version": 1,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "entries": entries,
        }
        self._atomic_write(payload)

    def _atomic_write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = None, None
        try:
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as temp:
                fd = temp.fileno()
                temp_name = temp.name
                json.dump(payload, temp, ensure_ascii=False, indent=2)
                temp.flush()
                os.fsync(fd)
            os.replace(temp_name, self.path)
            temp_name = None
        finally:
            if temp_name:
                try:
                    Path(temp_name).unlink(missing_ok=True)
                except OSError:
                    pass
