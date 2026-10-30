from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SettingSpec:
    key: str
    label: str
    hint: str = ""
    kind: str = "text"


@dataclass(frozen=True, slots=True)
class SettingSection:
    key: str
    title: str
    description: str
    settings: tuple[SettingSpec, ...]


SETTINGS_SECTIONS = (
    SettingSection(
        "general",
        "General",
        "Preferencias básicas de Tecnocity Admin.",
        (
            SettingSpec("business_name", "Nombre del negocio", "Se usará en futuras salidas y documentos."),
            SettingSpec("currency", "Moneda", "Código ISO de la moneda."),
        ),
    ),
    SettingSection(
        "appearance",
        "Apariencia",
        "Tema visual de la aplicación. Los cambios se guardan para los próximos inicios.",
        (
            SettingSpec("theme", "Tema", "Claro, oscuro o futurista morado.", "select"),
        ),
    ),
    SettingSection(
        "backup",
        "Copias de seguridad",
        "Configuración del respaldo local y Google Drive.",
        (
            SettingSpec("schedule_time", "Hora automática", "Formato 24 horas, por ejemplo 23:00.", "time"),
            SettingSpec("keep_local_copies", "Copias locales a conservar", "Cantidad máxima de respaldos locales."),
        ),
    ),
)
