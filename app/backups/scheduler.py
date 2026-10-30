from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class WindowsBackupScheduler:
    """Small adapter around Windows Task Scheduler.

    The GUI configures the task; the task invokes ``run.py --backup-now`` so a
    backup can happen even when the main window is closed.
    """

    def __init__(self, *, project_root: Path, task_name: str) -> None:
        self.project_root = Path(project_root)
        self.task_name = task_name

    @property
    def supported(self) -> bool:
        return os.name == "nt"

    def install(self, time_24h: str) -> tuple[bool, str]:
        if not self.supported:
            return False, "La programación automática de Windows solo está disponible en Windows."
        if not _valid_time(time_24h):
            return False, "La hora debe tener el formato HH:MM."
        run_script = self.project_root / "run.py"
        if not run_script.exists():
            return False, f"No se encontró el archivo de ejecución: {run_script}"
        python_exe = Path(sys.executable)
        task_command = f'"{python_exe}" "{run_script}" --backup-now'
        args = [
            "schtasks",
            "/Create",
            "/TN", self.task_name,
            "/SC", "DAILY",
            "/ST", time_24h,
            "/TR", task_command,
            "/F",
        ]
        completed = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if completed.returncode != 0:
            return False, completed.stderr.strip() or completed.stdout.strip() or "No se pudo crear la tarea de Windows."
        return True, f"Tarea automática configurada diariamente a las {time_24h}."

    def uninstall(self) -> tuple[bool, str]:
        if not self.supported:
            return False, "La programación automática de Windows solo está disponible en Windows."
        completed = subprocess.run(
            ["schtasks", "/Delete", "/TN", self.task_name, "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            return False, completed.stderr.strip() or completed.stdout.strip() or "No se pudo eliminar la tarea."
        return True, "Tarea automática eliminada."

    def status(self) -> dict[str, str | bool]:
        if not self.supported:
            return {"installed": False, "supported": False, "detail": "No disponible en este sistema."}
        completed = subprocess.run(
            ["schtasks", "/Query", "/TN", self.task_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "installed": completed.returncode == 0,
            "supported": True,
            "detail": "Programada" if completed.returncode == 0 else "No instalada",
        }


def _valid_time(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
        return len(value) == 5
    except ValueError:
        return False
