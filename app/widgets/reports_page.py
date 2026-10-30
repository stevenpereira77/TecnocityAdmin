from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from PySide6.QtCore import Qt, QDate, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHeaderView

from app.reports import ReportResult, ReportService
from app.reports.exporters import export_csv, export_excel, export_pdf
from app.reports.print_service import print_report
from app.reports.qt_model import ReportTableModel


class ReportsPage(QWidget):
    """Professional report center: filters, preview, export and printing."""

    PERIODS = (
        ("Este mes", "month"),
        ("Hoy", "today"),
        ("Últimos 7 días", "7d"),
        ("Últimos 30 días", "30d"),
        ("Últimos 90 días", "90d"),
        ("Mes anterior", "previous_month"),
        ("Este año", "year"),
        ("Todo el historial", "all"),
    )

    def __init__(self, report_service: ReportService, export_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.report_service = report_service
        self.export_dir = export_dir / "reportes"
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.current_result: ReportResult | None = None
        self.current_model: ReportTableModel | None = None
        self.proxy_model: QSortFilterProxyModel | None = None
        self._building_custom = False
        self._build_ui()
        self._load_report_definitions()
        self._set_default_dates()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QWidget()
        content.setObjectName("pageContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(3)
        title = QLabel("Centro de reportes")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Consulta, filtra, exporta, genera PDF e imprime información administrativa con formato profesional.")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap, 1)

        self.status_badge = QLabel("Listo")
        self.status_badge.setObjectName("reportStatus")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setMinimumWidth(90)
        self.status_badge.setMinimumHeight(30)
        header.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        filters = QGroupBox("Filtros del reporte")
        filters_layout = QHBoxLayout(filters)
        filters_layout.setSpacing(9)

        self.report_combo = QComboBox()
        self.report_combo.setObjectName("reportFilter")
        self.report_combo.setMinimumWidth(205)
        self.report_combo.currentIndexChanged.connect(self._report_changed)
        filters_layout.addWidget(self.report_combo)

        self.period_combo = QComboBox()
        self.period_combo.setObjectName("reportFilter")
        for label, key in self.PERIODS:
            self.period_combo.addItem(label, key)
        self.period_combo.addItem("Personalizado", "custom")
        self.period_combo.currentIndexChanged.connect(self._period_changed)
        filters_layout.addWidget(self.period_combo)

        self.start_edit = QDateEdit()
        self.start_edit.setObjectName("reportDateFilter")
        self.start_edit.setCalendarPopup(True)
        self.start_edit.dateChanged.connect(self._date_changed)
        filters_layout.addWidget(self.start_edit)

        self.end_edit = QDateEdit()
        self.end_edit.setObjectName("reportDateFilter")
        self.end_edit.setCalendarPopup(True)
        self.end_edit.dateChanged.connect(self._date_changed)
        filters_layout.addWidget(self.end_edit)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("reportSearch")
        self.search_edit.setPlaceholderText("Buscar en el reporte...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(280)
        self.search_edit.textChanged.connect(self._search_changed)
        filters_layout.addWidget(self.search_edit, 1)

        refresh = QPushButton("Actualizar")
        refresh.setObjectName("secondaryButton")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.clicked.connect(self.refresh)
        filters_layout.addWidget(refresh)
        layout.addWidget(filters)

        actions = QGroupBox("Salida")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setSpacing(9)
        self.excel_button = self._action_button("Exportar Excel", "primaryButton")
        self.csv_button = self._action_button("Exportar CSV", "secondaryButton")
        self.pdf_button = self._action_button("Generar PDF", "secondaryButton")
        self.print_button = self._action_button("Imprimir", "secondaryButton")
        self.excel_button.clicked.connect(lambda: self._export("excel"))
        self.csv_button.clicked.connect(lambda: self._export("csv"))
        self.pdf_button.clicked.connect(lambda: self._export("pdf"))
        self.print_button.clicked.connect(self._print)
        for button in (self.excel_button, self.csv_button, self.pdf_button, self.print_button):
            actions_layout.addWidget(button)
        actions_layout.addStretch(1)
        self.range_label = QLabel()
        self.range_label.setObjectName("reportRange")
        actions_layout.addWidget(self.range_label)
        layout.addWidget(actions)

        self.summary_group = QGroupBox("Resumen del reporte")
        self.summary_layout = QHBoxLayout(self.summary_group)
        self.summary_layout.setContentsMargins(10, 10, 10, 10)
        self.summary_cards: list[dict[str, QLabel]] = []
        for _ in range(4):
            self._make_summary_card()
        layout.addWidget(self.summary_group)

        preview = QGroupBox("Vista previa")
        preview_layout = QVBoxLayout(preview)
        self.table = QTableView()
        self.table.setObjectName("reportTable")
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout.addWidget(self.table)
        layout.addWidget(preview, 1)

        footer = QHBoxLayout()
        self.result_count = QLabel()
        self.result_count.setObjectName("mutedText")
        footer.addWidget(self.result_count)
        footer.addStretch(1)
        hint = QLabel("Consejo: aplica el filtro y luego exporta; la exportación respeta la búsqueda actual.")
        hint.setObjectName("hintText")
        footer.addWidget(hint)
        layout.addLayout(footer)

        root.addWidget(content)

        self._date_widgets = (self.start_edit, self.end_edit)
        self._set_date_widgets_visible(False)

    @staticmethod
    def _action_button(text: str, object_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _make_summary_card(self) -> None:
        frame = QFrame()
        frame.setObjectName("reportSummaryCard")
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 9, 12, 9)
        label = QLabel("—")
        label.setObjectName("reportSummaryLabel")
        value = QLabel("—")
        value.setObjectName("reportSummaryValue")
        box.addWidget(label)
        box.addWidget(value)
        self.summary_layout.addWidget(frame, 1)
        self.summary_cards.append({"label": label, "value": value})

    def _load_report_definitions(self) -> None:
        self.report_combo.blockSignals(True)
        self.report_combo.clear()
        for definition in self.report_service.definitions():
            self.report_combo.addItem(definition.title, definition.key)
        self.report_combo.blockSignals(False)

    def _set_default_dates(self) -> None:
        today = QDate.currentDate()
        self.start_edit.setDate(today.addDays(-29))
        self.end_edit.setDate(today)

    def _set_date_widgets_visible(self, visible: bool) -> None:
        for widget in self._date_widgets:
            widget.setVisible(visible)

    def _report_changed(self) -> None:
        definition = self._current_definition()
        date_enabled = bool(definition and definition.date_filtered)
        self.period_combo.setEnabled(date_enabled)
        self._set_date_widgets_visible(date_enabled and self.period_combo.currentData() == "custom")
        if definition:
            self.search_edit.setPlaceholderText(definition.search_placeholder)
        self.refresh()

    def _period_changed(self) -> None:
        custom = self.period_combo.currentData() == "custom" and self.period_combo.isEnabled()
        self._set_date_widgets_visible(custom)
        if custom and not self._building_custom:
            self._set_default_dates()
        self.refresh()

    def _date_changed(self) -> None:
        if self.period_combo.currentData() == "custom" and self.period_combo.isEnabled():
            self.refresh()

    def _search_changed(self) -> None:
        if self.current_model is not None:
            self._apply_search()
            self._update_result_counter()

    def _current_definition(self):
        key = self.report_combo.currentData()
        return self.report_service.definitions()[self.report_combo.currentIndex()] if key is not None and self.report_combo.currentIndex() >= 0 else None

    def _range_kwargs(self) -> dict:
        if self.period_combo.currentData() != "custom":
            return {"period": str(self.period_combo.currentData() or "month")}
        start_date = self.start_edit.date()
        end_date = self.end_edit.date()
        start = datetime(start_date.year(), start_date.month(), start_date.day())
        end = datetime(end_date.year(), end_date.month(), end_date.day(), 23, 59, 59, 999999)
        return {"period": "custom", "start": start, "end": end}

    def refresh(self) -> None:
        definition = self._current_definition()
        if definition is None:
            return
        try:
            kwargs = self._range_kwargs()
            self.current_result = self.report_service.build(definition.key, **kwargs)
        except ValueError as exc:
            self._set_status("Error", error=True)
            QMessageBox.warning(self, "Rango inválido", str(exc))
            return
        except Exception as exc:
            self._set_status("Error", error=True)
            QMessageBox.critical(self, "No se pudo generar el reporte", str(exc))
            return

        self.current_model = ReportTableModel(self.current_result, self)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.current_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)
        self.table.setModel(self.proxy_model)
        self._apply_search()
        self.table.resizeColumnsToContents()
        self._configure_headers()
        self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)

        self._update_summary()
        self._update_range_label()
        self._update_result_counter()
        self._set_status("Listo")
        has_rows = bool(self.current_result.rows)
        for button in (self.excel_button, self.csv_button, self.pdf_button, self.print_button):
            button.setEnabled(True)
        if not has_rows:
            self._set_status("Sin datos")

    def _configure_headers(self) -> None:
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for index in range(header.count()):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
        if header.count():
            # Keep long detail columns usable while allowing horizontal scrolling.
            last = header.count() - 1
            header.setSectionResizeMode(last, QHeaderView.ResizeMode.Interactive)
            header.setMinimumSectionSize(72)

    def _apply_search(self) -> None:
        if self.proxy_model is not None:
            self.proxy_model.setFilterFixedString(self.search_edit.text().strip())

    def _update_summary(self) -> None:
        assert self.current_result is not None
        summary = list(self.current_result.summary)[:4]
        while len(summary) < 4:
            summary.append(("—", "—", "text"))
        from app.reports.formatting import format_value
        for card, (label, value, kind) in zip(self.summary_cards, summary):
            card["label"].setText(str(label))
            card["value"].setText(format_value(value, kind))

    def _update_range_label(self) -> None:
        from app.reports.formatting import format_period
        assert self.current_result is not None
        self.range_label.setText(format_period(self.current_result.start, self.current_result.end))

    def _update_result_counter(self) -> None:
        if self.current_model is None:
            return
        visible = len(self.current_model.filtered_rows(self.search_edit.text()))
        total = self.current_model.rowCount()
        self.result_count.setText(f"{visible:,} registros visibles · {total:,} totales".replace(",", "."))

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_badge.setText(text)
        self.status_badge.setProperty("state", "error" if error else "ok")
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def _filtered_rows(self):
        if self.current_result is None:
            return tuple()
        if self.current_model is None:
            return self.current_result.rows
        return self.current_model.filtered_rows(self.search_edit.text())

    def _default_path(self, extension: str) -> Path:
        assert self.current_result is not None
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^A-Za-z0-9_-]+", "_", self.current_result.definition.key).strip("_")
        return self.export_dir / f"Tecnocity_{slug}_{now}.{extension}"

    def _export(self, kind: str) -> None:
        if self.current_result is None:
            return
        extensions = {"excel": "xlsx", "csv": "csv", "pdf": "pdf"}
        labels = {"excel": "Excel (*.xlsx)", "csv": "CSV (*.csv)", "pdf": "PDF (*.pdf)"}
        extension = extensions[kind]
        selected, _ = QFileDialog.getSaveFileName(
            self,
            f"Exportar {self.current_result.definition.title}",
            str(self._default_path(extension)),
            labels[kind],
        )
        if not selected:
            return
        destination = Path(selected)
        if destination.suffix.lower() != f".{extension}":
            destination = destination.with_suffix(f".{extension}")
        try:
            rows = self._filtered_rows()
            if kind == "excel":
                path = export_excel(self.current_result, destination, rows)
            elif kind == "csv":
                path = export_csv(self.current_result, destination, rows)
            else:
                path = export_pdf(self.current_result, destination, rows)
        except Exception as exc:
            self._set_status("Error", error=True)
            QMessageBox.critical(self, "Exportación fallida", str(exc))
            return
        self._set_status("Exportado")
        QMessageBox.information(self, "Exportación completada", f"El archivo fue generado correctamente:\n\n{path}")

    def _print(self) -> None:
        if self.current_result is None:
            return
        try:
            accepted = print_report(self, self.current_result, self._filtered_rows())
        except Exception as exc:
            self._set_status("Error", error=True)
            QMessageBox.critical(self, "Impresión no disponible", str(exc))
            return
        if accepted:
            self._set_status("Impreso")
