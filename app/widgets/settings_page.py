from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QMessageBox,
    QInputDialog,
)

from app.backups import BackupManager, BackupStatus, WindowsBackupScheduler
from app.config import AppSettings, SettingsStore
from app.theme import ThemeManager
from app.widgets.appearance_section import AppearanceSection
from app.widgets.ui_helpers import add_table_columns, fit_table, show_error, show_info

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SettingsPage(QWidget):
    """Professional configuration center; sections are intentionally isolated."""

    def __init__(self, settings: AppSettings, settings_store: SettingsStore, backup: BackupManager, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.settings = settings
        self.settings_store = settings_store
        self.backup = backup
        self.theme_manager = theme_manager
        task_name = str(settings_store.get("backup", "windows_task_name", "Tecnocity Admin - Backup Automático"))
        self.scheduler = WindowsBackupScheduler(project_root=settings.project_root, task_name=task_name)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 28)
        root.setSpacing(14)

        title = QLabel("Configuración")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        subtitle = QLabel("Administra preferencias, respaldos locales, Google Drive y automatización desde un solo lugar.")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("pageContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 8, 16)
        layout.setSpacing(16)

        layout.addWidget(self._build_appearance_section())
        layout.addWidget(self._build_general_section())
        layout.addWidget(self._build_google_section())
        layout.addWidget(self._build_schedule_section())
        layout.addWidget(self._build_backup_history_section())
        layout.addWidget(self._build_restore_section())
        layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _build_appearance_section(self) -> QGroupBox:
        box = QGroupBox("Apariencia")
        box.setObjectName("settingsSection")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.appearance = AppearanceSection(self.theme_manager)
        self.appearance.theme_applied.connect(self._theme_applied)
        layout.addWidget(self.appearance)
        return box

    def _build_general_section(self) -> QGroupBox:
        box = QGroupBox("General")
        box.setObjectName("settingsSection")
        form = QFormLayout(box)
        form.setContentsMargins(16, 18, 16, 16)
        self.business_name = QLineEdit()
        self.business_name.setPlaceholderText("Tecnocity")
        self.currency = QComboBox()
        self.currency.addItems(["COP", "USD", "EUR", "MXN", "ARS", "CLP"])
        form.addRow("Nombre del negocio", self.business_name)
        form.addRow("Moneda", self.currency)
        save = QPushButton("Guardar preferencias")
        save.setObjectName("primaryButton")
        save.clicked.connect(self.save_general)
        form.addRow("", save)
        return box

    def _build_google_section(self) -> QGroupBox:
        box = QGroupBox("Google Drive · Respaldo en la nube")
        box.setObjectName("settingsSection")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(10)

        status_row = QHBoxLayout()
        self.google_status = QLabel()
        self.google_status.setObjectName("settingsStatus")
        status_row.addWidget(self.google_status, 1)
        self.btn_connect = QPushButton("Conectar / cambiar cuenta")
        self.btn_connect.setObjectName("primaryButton")
        self.btn_connect.clicked.connect(self.connect_google)
        status_row.addWidget(self.btn_connect)
        self.btn_disconnect = QPushButton("Desconectar")
        self.btn_disconnect.setObjectName("secondaryButton")
        self.btn_disconnect.clicked.connect(self.disconnect_google)
        status_row.addWidget(self.btn_disconnect)
        layout.addLayout(status_row)

        credential_row = QHBoxLayout()
        self.credentials_path = QLineEdit()
        self.credentials_path.setReadOnly(True)
        self.credentials_path.setPlaceholderText("Selecciona el JSON de credenciales OAuth que descargas de Google Cloud")
        credential_row.addWidget(self.credentials_path, 1)
        btn_credentials = QPushButton("Seleccionar credenciales…")
        btn_credentials.setObjectName("secondaryButton")
        btn_credentials.clicked.connect(self.select_credentials)
        credential_row.addWidget(btn_credentials)
        layout.addLayout(credential_row)

        destination = QFormLayout()
        self.destination_email = QLineEdit()
        self.destination_email.setPlaceholderText("correo@ejemplo.com")
        self.destination_email.setToolTip("La cuenta conectada crea y posee las copias. Este correo adicional recibe acceso a la carpeta compartida.")
        self.folder_name = QLineEdit()
        self.folder_name.setPlaceholderText("Tecnocity Admin - Backups")
        self.google_enabled = QCheckBox("Activar copias automáticas en Google Drive")
        destination.addRow("Correo destino / compartido", self.destination_email)
        destination.addRow("Carpeta en Google Drive", self.folder_name)
        destination.addRow("", self.google_enabled)
        layout.addLayout(destination)

        hint = QLabel(
            "Importante: el correo que conectas con Google es la cuenta que crea la carpeta y posee los respaldos. "
            "El correo destino adicional recibe acceso a esa carpeta sin tocar código."
        )
        hint.setObjectName("hintText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        action_row = QHBoxLayout()
        save = QPushButton("Guardar configuración de Drive")
        save.setObjectName("primaryButton")
        save.clicked.connect(self.save_google_settings)
        action_row.addWidget(save)
        test = QPushButton("Crear respaldo y verificar ahora")
        test.setObjectName("secondaryButton")
        test.clicked.connect(lambda: self.run_backup("manual"))
        action_row.addWidget(test)
        action_row.addStretch(1)
        layout.addLayout(action_row)
        return box

    def _build_schedule_section(self) -> QGroupBox:
        box = QGroupBox("Automatización")
        box.setObjectName("settingsSection")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(10)

        row = QHBoxLayout()
        self.schedule_enabled = QCheckBox("Programar respaldo automático diario")
        self.schedule_time = QLineEdit()
        self.schedule_time.setMaximumWidth(110)
        self.schedule_time.setPlaceholderText("23:00")
        row.addWidget(self.schedule_enabled)
        row.addWidget(QLabel("Hora (24 h):"))
        row.addWidget(self.schedule_time)
        row.addStretch(1)
        layout.addLayout(row)

        self.backup_on_startup = QCheckBox("Comprobar al iniciar Tecnocity si falta un respaldo del día")
        layout.addWidget(self.backup_on_startup)

        keep_row = QHBoxLayout()
        keep_row.addWidget(QLabel("Copias locales a conservar:"))
        self.keep_local = QSpinBox()
        self.keep_local.setObjectName("settingsSpin")
        self.keep_local.setRange(1, 100)
        keep_row.addWidget(self.keep_local)
        keep_row.addStretch(1)
        layout.addLayout(keep_row)

        buttons = QHBoxLayout()
        self.btn_install_task = QPushButton("Configurar tarea automática de Windows")
        self.btn_install_task.setObjectName("primaryButton")
        self.btn_install_task.clicked.connect(self.install_task)
        buttons.addWidget(self.btn_install_task)
        self.btn_remove_task = QPushButton("Eliminar tarea")
        self.btn_remove_task.setObjectName("secondaryButton")
        self.btn_remove_task.clicked.connect(self.remove_task)
        buttons.addWidget(self.btn_remove_task)
        self.task_status = QLabel()
        self.task_status.setObjectName("settingsStatus")
        buttons.addWidget(self.task_status, 1)
        layout.addLayout(buttons)

        save = QPushButton("Guardar automatización")
        save.setObjectName("secondaryButton")
        save.clicked.connect(self.save_schedule_clicked)
        layout.addWidget(save, 0, Qt.AlignLeft)

        hint = QLabel("La tarea de Windows permite hacer el respaldo aunque la ventana de Tecnocity esté cerrada. La PC debe poder ejecutar la tarea programada.")
        hint.setObjectName("hintText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return box

    def _build_backup_history_section(self) -> QGroupBox:
        box = QGroupBox("Estado y movimientos de respaldo")
        box.setObjectName("settingsSection")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 16)
        self.last_backup_label = QLabel()
        self.last_backup_label.setObjectName("summaryLabel")
        layout.addWidget(self.last_backup_label)

        self.history_table = QTableWidget()
        self.history_table.setObjectName("backupHistory")
        add_table_columns(self.history_table, ["Fecha", "Estado", "Destino", "Verificado", "Archivo", "Detalle"])
        self.history_table.setMinimumHeight(220)
        layout.addWidget(self.history_table)
        refresh = QPushButton("Actualizar estado")
        refresh.setObjectName("secondaryButton")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh, 0, Qt.AlignLeft)
        return box

    def _build_restore_section(self) -> QGroupBox:
        box = QGroupBox("Restauración")
        box.setObjectName("settingsSection")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(16, 18, 16, 16)
        warning = QLabel(
            "Restaurar reemplaza la base de datos actual. Antes de hacerlo se crea automáticamente un respaldo de seguridad "
            "PreRestore_YYYY-MM-DD_HH-MM-SS.db."
        )
        warning.setObjectName("hintText")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        row = QHBoxLayout()
        local = QPushButton("Restaurar desde archivo local…")
        local.setObjectName("secondaryButton")
        local.clicked.connect(self.restore_local)
        row.addWidget(local)
        drive = QPushButton("Restaurar desde Google Drive…")
        drive.setObjectName("secondaryButton")
        drive.clicked.connect(self.restore_google)
        row.addWidget(drive)
        open_folder = QPushButton("Abrir carpeta de respaldos")
        open_folder.setObjectName("secondaryButton")
        open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.settings.backups_dir))))
        row.addWidget(open_folder)
        row.addStretch(1)
        layout.addLayout(row)
        return box

    def refresh(self) -> None:
        general = self.settings_store.section("general")
        self.appearance.refresh()
        backup = self.settings_store.section("backup")
        self.business_name.setText(str(general.get("business_name", "Tecnocity")))
        currency = str(general.get("currency", "COP"))
        index = self.currency.findText(currency)
        self.currency.setCurrentIndex(max(index, 0))
        self.destination_email.setText(str(backup.get("google_destination_email", "")))
        self.folder_name.setText(str(backup.get("google_folder_name", "Tecnocity Admin - Backups")))
        self.google_enabled.setChecked(bool(backup.get("google_enabled", True)))
        self.schedule_enabled.setChecked(bool(backup.get("schedule_enabled", False)))
        self.schedule_time.setText(str(backup.get("schedule_time", "23:00")))
        self.backup_on_startup.setChecked(bool(backup.get("backup_on_startup", False)))
        self.keep_local.setValue(max(1, int(backup.get("keep_local_copies", 10))))
        self.credentials_path.setText(str(self.backup.google.credentials_path) if self.backup.google.credentials_path.exists() else "")
        status = self.backup.google_status()
        if status["connected"]:
            self.google_status.setText(f"● Conectado · {status['email']}")
        else:
            self.google_status.setText("● Google Drive no conectado")
        task = self.scheduler.status()
        self.task_status.setText(str(task["detail"]))
        self.btn_install_task.setEnabled(self.scheduler.supported)
        self.btn_remove_task.setEnabled(self.scheduler.supported and bool(task.get("installed")))
        self._refresh_history()

    def _theme_applied(self, key: str) -> None:
        # MainWindow owns application-wide stylesheet application; this page only persists the preference.
        callback = self.window()
        if callback is not None and hasattr(callback, "apply_theme"):
            callback.apply_theme(key)

    def save_general(self) -> None:
        self.settings_store.update_section("general", {
            "business_name": self.business_name.text().strip() or "Tecnocity",
            "currency": self.currency.currentText(),
        })
        self.settings_store.save()
        show_info(self, "Preferencias guardadas correctamente.")

    def save_google_settings(self) -> bool:
        email = self.destination_email.text().strip()
        if email and not EMAIL_RE.match(email):
            show_error(self, "El correo destino no tiene un formato válido.")
            return False
        folder = self.folder_name.text().strip() or "Tecnocity Admin - Backups"
        self.settings_store.update_section("backup", {
            "google_destination_email": email,
            "google_folder_name": folder,
            "google_enabled": self.google_enabled.isChecked(),
        })
        self.settings_store.save()
        show_info(self, "Configuración de Google Drive guardada. Se aplicará al próximo respaldo.")
        return True

    def save_schedule(self) -> bool:
        value = self.schedule_time.text().strip()
        try:
            datetime.strptime(value, "%H:%M")
            if len(value) != 5:
                raise ValueError
        except ValueError:
            show_error(self, "La hora debe tener el formato HH:MM, por ejemplo 23:00.")
            return False
        self.settings_store.update_section("backup", {
            "schedule_enabled": self.schedule_enabled.isChecked(),
            "schedule_time": value,
            "backup_on_startup": self.backup_on_startup.isChecked(),
            "keep_local_copies": self.keep_local.value(),
        })
        self.settings_store.save()
        return True

    def select_credentials(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Seleccionar credenciales OAuth de Google", "", "JSON (*.json)")
        if not source:
            return
        try:
            payload = json.loads(Path(source).read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or "installed" not in payload:
                raise ValueError("Selecciona un JSON de credenciales OAuth de tipo Desktop app (installed).")
            target = self.backup.google.credentials_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.refresh()
            show_info(self, "Credenciales guardadas localmente. Ahora puedes conectar la cuenta de Google.")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            show_error(self, f"No se pudieron guardar las credenciales: {exc}")

    def connect_google(self) -> None:
        try:
            identity = self.backup.authenticate_google(force_reauth=True)
            if not self.destination_email.text().strip():
                self.destination_email.setText(identity.get("email", ""))
            self.save_google_settings()
            self.refresh()
            show_info(self, f"Google Drive conectado con {identity.get('email', 'la cuenta seleccionada')}.")
        except Exception as exc:
            show_error(self, str(exc))

    def disconnect_google(self) -> None:
        answer = QMessageBox.question(self, "Desconectar Google Drive", "¿Quieres quitar la sesión de Google Drive de este equipo?")
        if answer != QMessageBox.Yes:
            return
        try:
            self.backup.disconnect_google()
            self.refresh()
        except Exception as exc:
            show_error(self, str(exc))

    def install_task(self) -> None:
        if not self.save_schedule():
            return
        ok, message = self.scheduler.install(self.schedule_time.text().strip())
        if not ok:
            show_error(self, message)
            return
        self.refresh()
        show_info(self, message)

    def remove_task(self) -> None:
        ok, message = self.scheduler.uninstall()
        if not ok:
            show_error(self, message)
            return
        self.refresh()
        show_info(self, message)

    def run_backup(self, reason: str) -> None:
        if not self.save_google_settings() or not self.save_schedule():
            return
        try:
            result = self.backup.backup_now(reason=reason)
        except Exception as exc:
            show_error(self, str(exc))
            return
        self._refresh_history()
        if result.status is BackupStatus.SUCCESS:
            show_info(self, result.message)
        elif result.status is BackupStatus.PARTIAL:
            QMessageBox.warning(self, "Respaldo parcial", result.message)
        else:
            show_error(self, result.message)

    def restore_local(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Seleccionar respaldo .db", str(self.settings.backups_dir), "Base de datos (*.db)")
        if not source:
            return
        if QMessageBox.question(self, "Confirmar restauración", "La base de datos actual será reemplazada. ¿Continuar?") != QMessageBox.Yes:
            return
        try:
            safety = self.backup.restore_local(Path(source))
            show_info(self, f"Base de datos restaurada. Respaldo de seguridad: {safety.name}. Reinicia Tecnocity Admin para refrescar todas las vistas.")
        except Exception as exc:
            show_error(self, str(exc))

    def restore_google(self) -> None:
        try:
            files = self.backup.list_remote_backups(limit=100)
        except Exception as exc:
            show_error(self, str(exc))
            return
        if not files:
            show_info(self, "No se encontraron respaldos de Google Drive en la carpeta configurada.")
            return
        choices = [str(f.get("name", "Sin nombre")) for f in files]
        selected, ok = QInputDialog.getItem(
            self,
            "Respaldos disponibles en Google Drive",
            "Selecciona el respaldo a restaurar:",
            choices,
            0,
            False,
        )
        if not ok:
            return
        selected_file = files[choices.index(selected)]
        if QMessageBox.question(self, "Confirmar restauración", "La base de datos actual será reemplazada. ¿Continuar?") != QMessageBox.Yes:
            return
        try:
            safety = self.backup.restore_google(str(selected_file.get("id", "")))
            show_info(self, f"Base de datos restaurada. Respaldo de seguridad: {safety.name}. Reinicia Tecnocity Admin para refrescar todas las vistas.")
        except Exception as exc:
            show_error(self, str(exc))

    def save_schedule_clicked(self) -> None:
        if self.save_schedule():
            show_info(self, "Configuración de automatización guardada.")

    def _refresh_history(self) -> None:
        entries = self.backup.history.list(limit=30)
        self.history_table.setRowCount(0)
        for entry in entries:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            values = [
                str(entry.get("created_at", "")),
                str(entry.get("status", "")),
                str(entry.get("destination", "")),
                "Sí" if entry.get("verified") else "No",
                str(entry.get("drive_file_name") or Path(str(entry.get("local_path", ""))).name),
                str(entry.get("message", "")),
            ]
            for col, value in enumerate(values):
                self.history_table.setItem(row, col, QTableWidgetItem(value))
        fit_table(self.history_table, stretch_column=5)
        if entries:
            first = entries[0]
            self.last_backup_label.setText(f"Último intento: {first.get('created_at', '—')} · {first.get('status', '—')} · {first.get('message', '')}")
        else:
            self.last_backup_label.setText("Aún no hay ejecuciones registradas de respaldo.")
