from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from app.calculations.financial import money


def parse_money(text: str | None) -> Decimal:
    raw = (text or "").strip().replace("$", "").replace(" ", "")
    if not raw:
        return Decimal("0.00")
    # Acepta 1000.00, 1000,00 y 1.000,00.
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    elif "." in raw and len(raw.rsplit(".", 1)[1]) == 3:
        raw = raw.replace(".", "")
    try:
        return money(Decimal(raw))
    except (InvalidOperation, ValueError):
        raise ValueError("Ingresa un importe válido.") from None


def fmt_money(value: Decimal | int | str) -> str:
    v = money(value)
    return f"$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def show_error(parent, message: str) -> None:
    QMessageBox.critical(parent, "No se pudo completar", message)


def show_info(parent, message: str) -> None:
    QMessageBox.information(parent, "Tecnocity Admin", message)


def confirm(parent, title: str, message: str) -> bool:
    return QMessageBox.question(parent, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes


def make_lineedit(placeholder: str = "") -> QLineEdit:
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    return edit


def make_money_edit(placeholder: str = "0,00") -> QLineEdit:
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    edit.setText("0,00")
    edit.setAlignment(Qt.AlignRight)
    return edit


def add_table_columns(table: QTableWidget, headers: list[str]) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setSelectionMode(QTableWidget.SingleSelection)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setWordWrap(False)
    table.setSortingEnabled(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(36)
    table.horizontalHeader().setMinimumSectionSize(70)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)


def add_row(table: QTableWidget, values: list[str]) -> None:
    row = table.rowCount()
    table.insertRow(row)
    for col, value in enumerate(values):
        item = QTableWidgetItem(str(value))
        if col == len(values) - 1:
            item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, col, item)


def fit_table(table: QTableWidget, stretch_column: int = 0) -> None:
    """Ajusta columnas al contenido y deja una sola columna elástica (sin textos cortados)."""
    header = table.horizontalHeader()
    for col in range(table.columnCount()):
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
    header.setMinimumSectionSize(90)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
