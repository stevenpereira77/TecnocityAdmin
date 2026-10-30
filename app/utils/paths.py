"""Filesystem path helpers for source and PyInstaller distributions."""
from pathlib import Path
import sys


def project_root() -> Path:
    """Return the folder containing bundled resources or the source repository."""
    bundle_root = getattr(sys, "_MEIPASS", None) if getattr(sys, "frozen", False) else None
    if bundle_root:
        return Path(bundle_root).resolve()
    return Path(__file__).resolve().parents[2]
