from __future__ import annotations

from pathlib import Path
import re

from app.config.settings_store import SettingsStore
from app.theme import ThemeManager, ThemePalette

ROOT = Path(__file__).resolve().parents[1]
TOKEN_RE = re.compile(r"__THEME_[A-Z0-9_]+__")
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")


def test_appearance_theme_is_persistent(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    manager = ThemeManager(ROOT, store)

    assert manager.current_key() == "light"
    manager.save_theme("futuristic")

    reloaded = SettingsStore(tmp_path / "settings.json")
    manager_reloaded = ThemeManager(ROOT, reloaded)
    assert manager_reloaded.current_key() == "futuristic"
    assert manager_reloaded.get_theme("unknown").key == "light"


def test_all_registered_themes_build_from_one_shared_stylesheet(tmp_path):
    manager = ThemeManager(ROOT, SettingsStore(tmp_path / "settings.json"))
    styles = [manager.stylesheet(theme.key) for theme in manager.available_themes()]
    assert all(style.strip() for style in styles)
    assert all(style.count("{") == style.count("}") for style in styles)
    assert all("__THEME_" not in style for style in styles)
    assert len(set(styles)) == len(styles)


def test_shared_stylesheet_has_no_unresolved_theme_tokens(tmp_path):
    manager = ThemeManager(ROOT, SettingsStore(tmp_path / "settings.json"))
    template = (ROOT / "assets" / "app.qss").read_text(encoding="utf-8")
    tokens = set(TOKEN_RE.findall(template))
    assert tokens
    expected = {f"__THEME_{key}__" for key in manager.get_theme("light").palette.tokens()}
    assert tokens <= expected


def test_theme_palette_is_complete_and_reuses_semantic_colors(tmp_path):
    manager = ThemeManager(ROOT, SettingsStore(tmp_path / "settings.json"))
    assert isinstance(manager.get_theme("light").palette, ThemePalette)
    for theme in manager.available_themes():
        palette = theme.palette
        assert len(palette.chart_series) >= 6
        assert all(HEX_RE.fullmatch(color) for color in palette.tokens().values())
        assert palette.primary
        assert palette.surface
        assert palette.input_bg
        assert palette.chart_bg
        assert palette.chart_plot_bg


def _hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _luminance(value: str) -> float:
    channels = []
    for channel in _hex_rgb(value):
        normalized = channel / 255
        channels.append(normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a: str, b: str) -> float:
    left, right = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (left + 0.05) / (right + 0.05)


def test_primary_text_and_chart_labels_have_safe_contrast(tmp_path):
    manager = ThemeManager(ROOT, SettingsStore(tmp_path / "settings.json"))
    for theme in manager.available_themes():
        palette = theme.palette
        assert _contrast(palette.text, palette.surface) >= 4.5
        assert _contrast(palette.chart_text, palette.chart_bg) >= 4.5
        assert _contrast(palette.chart_axis, palette.chart_bg) >= 3.0
        assert _contrast(palette.primary, palette.text_inverse) >= 3.0


def test_settings_store_includes_appearance_defaults(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    assert store.get("appearance", "theme") == "light"
