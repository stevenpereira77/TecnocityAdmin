from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_settings_page_is_modular_and_backup_focused():
    source = (ROOT / "app" / "widgets" / "settings_page.py").read_text(encoding="utf-8")
    assert "class SettingsPage" in source
    assert "Google Drive · Respaldo en la nube" in source
    assert "Restauración" in source
    assert "Programar respaldo automático diario" in source
    assert "Configurar tarea automática de Windows" in source
    assert "Crear respaldo y verificar ahora" in source


def test_main_window_registers_configuration_page_lazily():
    source = (ROOT / "app" / "views" / "main_window.py").read_text(encoding="utf-8")
    assert '"Configuración"' in source
    assert "def _settings_page_factory" in source
    assert "return SettingsPage(" in source
    assert "self.backup_manager" in source


def test_secret_and_local_backup_files_are_ignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/config/google/" in gitignore
    assert "client_secret.json" in gitignore
    assert "token.json" in gitignore
    assert "data/backups/*" in gitignore
    assert "*.db-*" in gitignore
    assert "data/config/settings.json" in gitignore


def test_settings_includes_extensible_appearance_section():
    source = (ROOT / "app" / "widgets" / "settings_page.py").read_text(encoding="utf-8")
    assert "AppearanceSection" in source
    assert "_build_appearance_section" in source
    assert "self.appearance.theme_applied.connect(self._theme_applied)" in source


def test_main_window_owns_theme_manager_and_applies_saved_theme():
    source = (ROOT / "app" / "views" / "main_window.py").read_text(encoding="utf-8")
    assert "ThemeManager" in source
    assert "self.theme_manager = ThemeManager" in source
    assert "self.apply_theme(self.theme_manager.current_key())" in source
    assert 'qapp.setProperty("tecnocityTheme", theme.key)' in source
