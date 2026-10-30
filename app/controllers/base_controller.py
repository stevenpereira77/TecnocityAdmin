"""Base controller contract."""
from __future__ import annotations


class BaseController:
    """Application-controller base for keeping UI logic out of domain services."""

    def start(self) -> None:
        """Hook for controller-specific initialization."""
