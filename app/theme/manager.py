from __future__ import annotations

from pathlib import Path
from typing import Final

from app.config import SettingsStore
from app.theme.themes import DEFAULT_THEME, THEMES, ThemeDefinition


APPEARANCE_SECTION: Final[str] = "appearance"
APPEARANCE_KEY: Final[str] = "theme"


class ThemeManager:
    """Loads, validates, applies and persists application themes."""

    TOKEN_PREFIX = "__THEME_"
    TOKEN_SUFFIX = "__"

    def __init__(self, project_root: Path, settings_store: SettingsStore) -> None:
        self.project_root = Path(project_root)
        self.settings_store = settings_store
        self._themes = {theme.key: theme for theme in THEMES}

    def available_themes(self) -> tuple[ThemeDefinition, ...]:
        return THEMES

    def get_theme(self, key: str | None) -> ThemeDefinition:
        if key and key in self._themes:
            return self._themes[key]
        return self._themes[DEFAULT_THEME]

    def current_key(self) -> str:
        key = str(self.settings_store.get(APPEARANCE_SECTION, APPEARANCE_KEY, DEFAULT_THEME))
        return self.get_theme(key).key

    def current_theme(self) -> ThemeDefinition:
        return self.get_theme(self.current_key())

    def save_theme(self, key: str) -> ThemeDefinition:
        theme = self.get_theme(key)
        self.settings_store.set(APPEARANCE_SECTION, APPEARANCE_KEY, theme.key)
        self.settings_store.save()
        return theme

    def stylesheet(self, key: str | None = None) -> str:
        """Build the shared QSS from the selected semantic palette."""
        theme = self.get_theme(key or self.current_key())
        template = (self.project_root / "assets" / "app.qss").read_text(encoding="utf-8")
        result = template.replace("__THEME_KEY__", theme.key)
        for token, value in theme.palette.tokens().items():
            result = result.replace(f"{self.TOKEN_PREFIX}{token}{self.TOKEN_SUFFIX}", value)
        return result

    def qt_palette(self, key: str | None = None):
        """Return a native QPalette aligned with the semantic theme."""
        from PySide6.QtGui import QColor, QPalette

        p = self.get_theme(key or self.current_key()).palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(p.app_bg))
        palette.setColor(QPalette.ColorRole.Base, QColor(p.input_bg))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(p.surface_alt))
        palette.setColor(QPalette.ColorRole.Button, QColor(p.secondary_bg))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(p.text))
        palette.setColor(QPalette.ColorRole.Text, QColor(p.text))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(p.text))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(p.text_subtle))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(p.selection_bg))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(p.selection_text))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(p.tooltip_bg))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(p.tooltip_text))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(p.disabled_text))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(p.disabled_text))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor(p.disabled_bg))
        return palette

    def apply_to(self, widget, key: str | None = None) -> ThemeDefinition:
        """Apply the selected stylesheet to a QWidget/QApplication-like object."""
        theme = self.get_theme(key or self.current_key())
        if hasattr(widget, "setStyleSheet"):
            widget.setStyleSheet(self.stylesheet(theme.key))
        return theme
