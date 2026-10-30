from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LazyPageHost(QWidget):
    """Lightweight stacked-page host that creates its real widget on first use.

    This keeps application startup cheap: hidden pages do not execute their
    database queries, build large tables, or import optional Qt modules until the
    user actually opens them.
    """

    def __init__(self, factory: Callable[[], QWidget], title: str, parent=None) -> None:
        super().__init__(parent)
        self._factory = factory
        self._widget: QWidget | None = None
        self._pending_theme = None
        self._loaded = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._layout = layout
        self._placeholder = QLabel(f"Preparando {title}…")
        self._placeholder.setObjectName("pageLoader")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setProperty("pageLoader", True)
        layout.addWidget(self._placeholder)

    def ensure_loaded(self) -> QWidget:
        if self._widget is not None:
            return self._widget
        widget = self._factory()
        self._layout.removeWidget(self._placeholder)
        self._placeholder.deleteLater()
        self._widget = widget
        self._layout.addWidget(widget)
        self._loaded = True
        if self._pending_theme is not None:
            handler = getattr(widget, "on_theme_changed", None)
            if callable(handler):
                handler(self._pending_theme)
        return widget

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def widget(self) -> QWidget | None:
        return self._widget

    def refresh(self) -> None:
        if self._widget is None:
            return
        handler = getattr(self._widget, "refresh", None)
        if callable(handler):
            handler()

    def refresh_products(self) -> None:
        if self._widget is None:
            return
        handler = getattr(self._widget, "refresh_products", None)
        if callable(handler):
            handler()

    def refresh_history(self) -> None:
        if self._widget is None:
            return
        handler = getattr(self._widget, "refresh_history", None)
        if callable(handler):
            handler()

    def on_theme_changed(self, theme) -> None:
        self._pending_theme = theme
        if self._widget is None:
            return
        handler = getattr(self._widget, "on_theme_changed", None)
        if callable(handler):
            handler(theme)
