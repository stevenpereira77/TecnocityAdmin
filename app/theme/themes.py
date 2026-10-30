from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.theme.palette import ThemePalette


@dataclass(frozen=True, slots=True)
class ThemeDefinition:
    """Metadata plus the semantic palette used by the application."""

    key: str
    label: str
    description: str
    palette: ThemePalette

    @property
    def accent(self) -> str:
        return self.palette.accent


THEMES: Final[tuple[ThemeDefinition, ...]] = (
    ThemeDefinition(
        key="light",
        label="Modo claro",
        description="Interfaz limpia y luminosa para el uso diario.",
        palette=ThemePalette(
            key="light", label="Modo claro", description="Interfaz limpia y luminosa para el uso diario.", accent="#2563EB",
            app_bg="#F6F8FC", sidebar_bg="#111827", sidebar_border="#1F2937",
            surface="#FFFFFF", surface_alt="#F8FAFC", surface_elevated="#FFFFFF", input_bg="#FFFFFF",
            border="#DFE5EE", border_strong="#CBD5E1", focus="#3B82F6",
            text="#172033", text_muted="#64748B", text_subtle="#94A3B8", text_inverse="#FFFFFF",
            primary="#2563EB", primary_hover="#1D4ED8", primary_pressed="#1E40AF",
            primary_soft="#DBEAFE", primary_soft_text="#1D4ED8",
            secondary_bg="#FFFFFF", secondary_hover="#F8FAFC", secondary_pressed="#EEF2F7",
            selection_bg="#DBEAFE", selection_text="#0F172A", header_bg="#EEF2F7", header_text="#475569", gridline="#E5EAF1",
            scrollbar="#CBD5E1", scrollbar_hover="#94A3B8", disabled_bg="#EEF2F7", disabled_text="#94A3B8",
            success="#15803D", success_bg="#ECFDF5", success_border="#BBF7D0",
            warning="#B45309", warning_bg="#FFF7ED", warning_border="#FED7AA",
            danger="#B91C1C", danger_bg="#FEF2F2", danger_border="#FECACA",
            info="#0369A1", info_bg="#F0F9FF", info_border="#BAE6FD",
            tooltip_bg="#111827", tooltip_text="#FFFFFF",
            chart_bg="#FFFFFF", chart_plot_bg="#FCFDFE", chart_grid="#E5EAF1", chart_axis="#64748B", chart_text="#334155",
            chart_series=("#2563EB", "#16A34A", "#DC2626", "#7C3AED", "#0D9488", "#D97706"),
        ),
    ),
    ThemeDefinition(
        key="dark",
        label="Modo oscuro",
        description="Reduce el brillo y ofrece una lectura cómoda en ambientes oscuros.",
        palette=ThemePalette(
            key="dark", label="Modo oscuro", description="Reduce el brillo y ofrece una lectura cómoda en ambientes oscuros.", accent="#8B5CF6",
            app_bg="#0F1117", sidebar_bg="#090B10", sidebar_border="#252A35",
            surface="#151922", surface_alt="#12161E", surface_elevated="#1B202A", input_bg="#11151D",
            border="#2A3040", border_strong="#343B4C", focus="#8B5CF6",
            text="#E5E7EB", text_muted="#9BA4B5", text_subtle="#687083", text_inverse="#FFFFFF",
            primary="#7C3AED", primary_hover="#6D28D9", primary_pressed="#5B21B6",
            primary_soft="#2E1D4B", primary_soft_text="#D8B4FE",
            secondary_bg="#151922", secondary_hover="#1D2330", secondary_pressed="#252C38",
            selection_bg="#3B256F", selection_text="#FFFFFF", header_bg="#1B202A", header_text="#B6BDCC", gridline="#252B37",
            scrollbar="#3B4251", scrollbar_hover="#566074", disabled_bg="#1D222C", disabled_text="#6B7280",
            success="#6EE7B7", success_bg="#12241B", success_border="#214C3A",
            warning="#FBBF24", warning_bg="#2A1C0F", warning_border="#5A3B1E",
            danger="#FCA5A5", danger_bg="#2B1518", danger_border="#5F272D",
            info="#7DD3FC", info_bg="#102A3B", info_border="#1F4B63",
            tooltip_bg="#F3F4F6", tooltip_text="#111827",
            chart_bg="#151922", chart_plot_bg="#12161E", chart_grid="#2A3040", chart_axis="#9BA4B5", chart_text="#D6D9E0",
            chart_series=("#60A5FA", "#6EE7B7", "#FCA5A5", "#A78BFA", "#67E8F9", "#FBBF24"),
        ),
    ),
    ThemeDefinition(
        key="futuristic",
        label="Futurista morado",
        description="Estética tecnológica premium con superficies oscuras, violeta y cian.",
        palette=ThemePalette(
            key="futuristic", label="Futurista morado", description="Estética tecnológica premium con superficies oscuras, violeta y cian.", accent="#A855F7",
            app_bg="#090712", sidebar_bg="#10081A", sidebar_border="#39204F",
            surface="#130D1D", surface_alt="#0F0A18", surface_elevated="#1A1028", input_bg="#0D0815",
            border="#352243", border_strong="#4A2B5E", focus="#C084FC",
            text="#F5EEFF", text_muted="#B9A8C9", text_subtle="#806B90", text_inverse="#FFFFFF",
            primary="#A855F7", primary_hover="#9333EA", primary_pressed="#7E22CE",
            primary_soft="#321451", primary_soft_text="#E9D5FF",
            secondary_bg="#130D1D", secondary_hover="#1C1129", secondary_pressed="#261737",
            selection_bg="#4C1D95", selection_text="#FFFFFF", header_bg="#1A1028", header_text="#D7C6E8", gridline="#2B1938",
            scrollbar="#56336F", scrollbar_hover="#72468F", disabled_bg="#1A1124", disabled_text="#6F5D7F",
            success="#67E8F9", success_bg="#102A2A", success_border="#205F61",
            warning="#FBBF24", warning_bg="#2B1B0E", warning_border="#6A421C",
            danger="#FDA4AF", danger_bg="#2A1019", danger_border="#622332",
            info="#7DD3FC", info_bg="#10243A", info_border="#214D70",
            tooltip_bg="#F4EDFF", tooltip_text="#170A25",
            chart_bg="#130D1D", chart_plot_bg="#0F0A18", chart_grid="#352243", chart_axis="#B9A8C9", chart_text="#E9DDF6",
            chart_series=("#C084FC", "#67E8F9", "#4ADE80", "#FBBF24", "#FB7185", "#60A5FA"),
        ),
    ),
)

DEFAULT_THEME = "light"
