"""Global exception handling for user-facing and technical errors."""
from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def install_exception_hook() -> None:
    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Excepción no controlada", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
