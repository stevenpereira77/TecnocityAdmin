from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from .formatting import format_value


class ReportTableModel(QAbstractTableModel):
    """Qt model over a ReportResult, keeping presentation separate from report logic."""

    def __init__(self, result, parent=None) -> None:
        super().__init__(parent)
        self.result = result
        self.rows = list(result.rows)
        self._sort_key = None
        self._sort_order = Qt.SortOrder.AscendingOrder

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.result.columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.result.columns):
            return self.result.columns[section].title
        return str(section + 1)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if not index.isValid():
            return None
        column = self.result.columns[index.column()]
        value = self.rows[index.row()].get(column.key)
        if role == Qt.ItemDataRole.DisplayRole:
            return format_value(value, column.kind)
        if role == Qt.ItemDataRole.UserRole:
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole and column.kind in {"money", "integer", "percent"}:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def set_rows(self, rows) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):  # noqa: N802
        if not 0 <= column < len(self.result.columns):
            return
        key = self.result.columns[column].key
        self.layoutAboutToBeChanged.emit()
        self.rows.sort(key=lambda row: self._sort_value(row.get(key)), reverse=order == Qt.SortOrder.DescendingOrder)
        self.layoutChanged.emit()
        self._sort_key = key
        self._sort_order = order

    @staticmethod
    def _sort_value(value):
        if value is None:
            return (0, "")
        if isinstance(value, (int, float, Decimal, datetime, date)):
            return (1, value)
        return (1, str(value).casefold())

    def filtered_rows(self, query: str):
        needle = (query or "").strip().casefold()
        if not needle:
            return tuple(self.rows)
        keys = [column.key for column in self.result.columns]
        return tuple(
            row for row in self.rows
            if needle in " ".join(str(row.get(key, "")) for key in keys).casefold()
        )
