from __future__ import annotations

import argparse
import sys

from app.config import AppSettings, SettingsStore
from app.core.error_handler import install_exception_hook
from app.core.logging_config import configure_logging
from app.database import create_database_engine, create_session_factory, initialize_database
from app.services import StoreService
from app.backups import BackupManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tecnocity Admin")
    parser.add_argument(
        "--backup-now",
        action="store_true",
        help="Crea y verifica un respaldo. Diseñado para Windows Task Scheduler.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = AppSettings.load()
    configure_logging(settings.logs_dir)

    engine = create_database_engine(settings.database_url)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    user_settings = SettingsStore(settings.user_settings_path)
    backup_manager = BackupManager(
        database_path=settings.database_path,
        backups_dir=settings.backups_dir,
        credentials_path=settings.google_credentials_path,
        token_path=settings.google_token_path,
        history_path=settings.backup_history_path,
        settings_store=user_settings,
        engine=engine,
    )

    if args.backup_now:
        if not bool(user_settings.get("backup", "schedule_enabled", False)):
            print("El respaldo automático está desactivado en Configuración.")
            engine.dispose()
            return 0
        try:
            result = backup_manager.backup_now(reason="scheduled")
            print(result.message)
            return 0 if result.success else 1
        finally:
            engine.dispose()

    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError as exc:
        print("PySide6 no está instalado. Ejecuta: python -m pip install -r requirements.txt", file=sys.stderr)
        return 2 if exc.name == "PySide6" else 1

    service = StoreService(session_factory)
    install_exception_hook()
    app = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
    app.setApplicationName(settings.app_name)
    app.setApplicationDisplayName(settings.app_name)
    app.setOrganizationName("Tecnocity")
    app.setStyle("Fusion")
    from app.views.main_window import MainWindow
    window = MainWindow(settings, service, user_settings, backup_manager)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
