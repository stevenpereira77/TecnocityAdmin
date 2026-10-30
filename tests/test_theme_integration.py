from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_has_no_legacy_hardcoded_theme_colors():
    source = (ROOT / "app/widgets/dashboard_page.py").read_text(encoding="utf-8")
    for literal in ("#2563eb", "#16a34a", "#dc2626", "#e2e8f0", "#64748b"):
        assert literal.lower() not in source.lower()
    assert "THEMES[0].palette" in source


def test_dashboard_has_theme_aware_chart_rendering():
    source = (ROOT / "app/widgets/dashboard_page.py").read_text(encoding="utf-8")
    charts = (ROOT / "app/widgets/dashboard_charts.py").read_text(encoding="utf-8")
    assert "def on_theme_changed" in source
    assert "chart.set_palette(palette)" in source
    assert "def set_palette" in charts
    assert "self.palette.chart_bg" in charts
    assert "self.palette.chart_series" in charts


def test_main_window_applies_application_wide_theme_and_notifies_page_hosts():
    source = (ROOT / "app/views/main_window.py").read_text(encoding="utf-8")
    assert "qapp.setStyleSheet" in source
    assert "qapp.setPalette" in source
    assert "page.on_theme_changed(theme)" in source
    assert "LazyPageHost" in source


def test_shared_qss_contains_no_raw_hex_colors():
    import re
    qss = (ROOT / "assets/app.qss").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9A-Fa-f]{6}", qss)


def test_shared_qss_defines_stable_metrics_and_native_popup_colors():
    qss = (ROOT / "assets/app.qss").read_text(encoding="utf-8")
    assert "QPushButton, QToolButton" in qss
    assert "min-height: 36px" in qss
    assert "QCalendarWidget QAbstractItemView" in qss
    assert "__THEME_INPUT_BG__" in qss
    assert "__THEME_SURFACE__" in qss
    assert "__THEME_PRIMARY__" in qss


def test_theme_specific_qss_files_are_no_longer_authoritative():
    assert not list((ROOT / "app/theme/styles").glob("light.qss"))
    assert not list((ROOT / "app/theme/styles").glob("dark.qss"))
    assert not list((ROOT / "app/theme/styles").glob("futuristic.qss"))
