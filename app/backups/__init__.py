"""Backup infrastructure: local snapshots, providers and scheduling."""
from .manager import BackupManager, BackupResult, BackupStatus
from .scheduler import WindowsBackupScheduler

__all__ = ["BackupManager", "BackupResult", "BackupStatus", "WindowsBackupScheduler"]
