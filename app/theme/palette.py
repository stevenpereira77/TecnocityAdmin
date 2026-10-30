from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThemePalette:
    """Semantic visual tokens used by both Qt widgets and dashboard charts.

    Adding a new theme should only require registering another ThemeDefinition
    with its own ThemePalette. Widgets must reference semantic roles, never
    hard-coded colors.
    """

    key: str
    label: str
    description: str
    accent: str

    app_bg: str
    sidebar_bg: str
    sidebar_border: str

    surface: str
    surface_alt: str
    surface_elevated: str
    input_bg: str

    border: str
    border_strong: str
    focus: str

    text: str
    text_muted: str
    text_subtle: str
    text_inverse: str

    primary: str
    primary_hover: str
    primary_pressed: str
    primary_soft: str
    primary_soft_text: str

    secondary_bg: str
    secondary_hover: str
    secondary_pressed: str

    selection_bg: str
    selection_text: str
    header_bg: str
    header_text: str
    gridline: str

    scrollbar: str
    scrollbar_hover: str
    disabled_bg: str
    disabled_text: str

    success: str
    success_bg: str
    success_border: str
    warning: str
    warning_bg: str
    warning_border: str
    danger: str
    danger_bg: str
    danger_border: str
    info: str
    info_bg: str
    info_border: str

    tooltip_bg: str
    tooltip_text: str

    chart_bg: str
    chart_plot_bg: str
    chart_grid: str
    chart_axis: str
    chart_text: str
    chart_series: tuple[str, ...]

    def tokens(self) -> dict[str, str]:
        """Return stylesheet token replacements using semantic names."""
        fields = {
            "APP_BG": self.app_bg,
            "SIDEBAR_BG": self.sidebar_bg,
            "SIDEBAR_BORDER": self.sidebar_border,
            "SURFACE": self.surface,
            "SURFACE_ALT": self.surface_alt,
            "SURFACE_ELEVATED": self.surface_elevated,
            "INPUT_BG": self.input_bg,
            "BORDER": self.border,
            "BORDER_STRONG": self.border_strong,
            "FOCUS": self.focus,
            "TEXT": self.text,
            "TEXT_MUTED": self.text_muted,
            "TEXT_SUBTLE": self.text_subtle,
            "TEXT_INVERSE": self.text_inverse,
            "PRIMARY": self.primary,
            "PRIMARY_HOVER": self.primary_hover,
            "PRIMARY_PRESSED": self.primary_pressed,
            "PRIMARY_SOFT": self.primary_soft,
            "PRIMARY_SOFT_TEXT": self.primary_soft_text,
            "SECONDARY_BG": self.secondary_bg,
            "SECONDARY_HOVER": self.secondary_hover,
            "SECONDARY_PRESSED": self.secondary_pressed,
            "SELECTION_BG": self.selection_bg,
            "SELECTION_TEXT": self.selection_text,
            "HEADER_BG": self.header_bg,
            "HEADER_TEXT": self.header_text,
            "GRIDLINE": self.gridline,
            "SCROLLBAR": self.scrollbar,
            "SCROLLBAR_HOVER": self.scrollbar_hover,
            "DISABLED_BG": self.disabled_bg,
            "DISABLED_TEXT": self.disabled_text,
            "SUCCESS": self.success,
            "SUCCESS_BG": self.success_bg,
            "SUCCESS_BORDER": self.success_border,
            "WARNING": self.warning,
            "WARNING_BG": self.warning_bg,
            "WARNING_BORDER": self.warning_border,
            "DANGER": self.danger,
            "DANGER_BG": self.danger_bg,
            "DANGER_BORDER": self.danger_border,
            "INFO": self.info,
            "INFO_BG": self.info_bg,
            "INFO_BORDER": self.info_border,
            "TOOLTIP_BG": self.tooltip_bg,
            "TOOLTIP_TEXT": self.tooltip_text,
            "CHART_BG": self.chart_bg,
            "CHART_PLOT_BG": self.chart_plot_bg,
            "CHART_GRID": self.chart_grid,
            "CHART_AXIS": self.chart_axis,
            "CHART_TEXT": self.chart_text,
        }
        for index, color in enumerate(self.chart_series, start=1):
            fields[f"CHART_SERIES_{index}"] = color
        return fields
