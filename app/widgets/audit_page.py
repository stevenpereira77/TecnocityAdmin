from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTableWidget, QVBoxLayout, QWidget

from app.services import StoreService
from .ui_helpers import add_row, add_table_columns


class AuditPage(QWidget):
    def __init__(self, service: StoreService):
        super().__init__()
        self.service = service
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)
        head = QHBoxLayout()
        wrap = QVBoxLayout()
        title = QLabel("Auditoría")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Historial de operaciones críticas del sistema; los registros no dependen de la interfaz.")
        subtitle.setObjectName("pageSubtitle")
        wrap.addWidget(title)
        wrap.addWidget(subtitle)
        head.addLayout(wrap)
        head.addStretch()
        button = QPushButton("Actualizar")
        button.setObjectName("secondaryButton")
        button.clicked.connect(self.refresh)
        head.addWidget(button)
        layout.addLayout(head)
        self.table = QTableWidget()
        add_table_columns(self.table, ["Fecha", "Acción", "Entidad", "ID", "Usuario", "Detalle"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

    def refresh(self):
        self.table.setRowCount(0)
        for entry in self.service.audit_logs():
            add_row(self.table, [entry.occurred_at.strftime("%Y-%m-%d %H:%M:%S"), entry.action, entry.entity_type, str(entry.entity_id or "-"), entry.user_name, entry.details])
