from __future__ import annotations

import math

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget, QVBoxLayout, QWidget

from app.services import StoreService
from .ui_helpers import add_row, add_table_columns, fmt_money, show_error, show_info
from .product_image_widgets import ProductImageDialog, product_pixmap


class StockAdjustmentDialog(QDialog):
    def __init__(self, products, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustar inventario")
        self.setMinimumWidth(430)
        form = QFormLayout(self)
        self.product = QComboBox()
        for p in products:
            self.product.addItem(f"{p.sku} · {p.name} · stock {p.stock_current}", p.id)
        self.qty = QSpinBox()
        self.qty.setRange(-1_000_000, 1_000_000)
        self.qty.setValue(1)
        self.qty.setToolTip("Positivo = entrada. Negativo = salida.")
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Ej.: Conteo físico")
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Observación opcional")
        form.addRow("Producto", self.product)
        form.addRow("Ajuste", self.qty)
        form.addRow("Motivo", self.reason)
        form.addRow("Observación", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        return self.product.currentData(), self.qty.value(), self.reason.text(), self.notes.text()


class InventoryPage(QWidget):
    """Inventory view with bounded pagination and a single SQL value query."""

    PAGE_SIZE = 100

    def __init__(self, service: StoreService):
        super().__init__()
        self.service = service
        self._page = 1
        self._total = 0
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 30)
        layout.setSpacing(14)
        head = QHBoxLayout()
        wrap = QVBoxLayout()
        t = QLabel("Inventario")
        t.setObjectName("pageTitle")
        s = QLabel("Existencias, valor FIFO y movimientos auditables.")
        s.setObjectName("pageSubtitle")
        wrap.addWidget(t)
        wrap.addWidget(s)
        head.addLayout(wrap)
        head.addStretch()
        adj = QPushButton("Ajustar stock")
        adj.setObjectName("secondaryButton")
        adj.clicked.connect(self.adjust_stock)
        head.addWidget(adj)
        b = QPushButton("Actualizar")
        b.setObjectName("secondaryButton")
        b.clicked.connect(self.refresh)
        head.addWidget(b)
        layout.addLayout(head)

        self.table = QTableWidget()
        add_table_columns(self.table, ["Foto", "SKU", "Producto", "Stock", "Mínimo", "Valor FIFO", "Estado"])
        self.table.setColumnWidth(0, 82)
        self._visible_inventory_rows = []
        self.table.cellClicked.connect(self._view_inventory_image)
        layout.addWidget(self.table, 1)

        pagination = QHBoxLayout()
        self.prev_page = QPushButton("‹ Anterior")
        self.next_page = QPushButton("Siguiente ›")
        self.page_status = QLabel("Página 1 de 1")
        self.page_status.setObjectName("summaryLabel")
        for button in (self.prev_page, self.next_page):
            button.setObjectName("secondaryButton")
        self.prev_page.clicked.connect(self._previous_page)
        self.next_page.clicked.connect(self._next_page)
        pagination.addWidget(self.prev_page)
        pagination.addWidget(self.page_status, 1)
        pagination.addWidget(self.next_page)
        layout.addLayout(pagination)

        label = QLabel("Historial reciente")
        label.setObjectName("sectionLabel")
        layout.addWidget(label)
        self.movements_table = QTableWidget()
        add_table_columns(self.movements_table, ["Fecha", "Producto", "Tipo", "Cantidad", "Documento", "Motivo"])
        layout.addWidget(self.movements_table, 1)

    def refresh(self):
        try:
            self._total = self.service.inventory_count()
            page_count = max(1, math.ceil(self._total / self.PAGE_SIZE))
            self._page = min(max(1, self._page), page_count)
            rows = self.service.inventory_rows(limit=self.PAGE_SIZE, offset=(self._page - 1) * self.PAGE_SIZE)
            movements = self.service.movements(limit=100)
        except Exception as exc:
            show_error(self, str(exc))
            return

        self.table.setRowCount(0)
        self._visible_inventory_rows = list(rows)
        for r in rows:
            add_row(self.table, ["", r["sku"], r["name"], str(r["stock"]), str(r["minimum"]), fmt_money(r["value"]), r["status"]])
            row_index = self.table.rowCount() - 1
            self.table.setRowHeight(row_index, 70)
            photo_item = self.table.item(row_index, 0)
            pixmap = product_pixmap(r, QSize(58, 58))
            if not pixmap.isNull():
                photo_item.setIcon(QIcon(pixmap))
                photo_item.setText("")
                photo_item.setToolTip("Clic para ampliar la imagen del producto")
            else:
                photo_item.setText("Sin foto")
                photo_item.setToolTip("Este producto todavía no tiene imagen")
            photo_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.movements_table.setRowCount(0)
        for m in movements:
            add_row(self.movements_table, [m.occurred_at.strftime("%Y-%m-%d %H:%M"), m.product.name, m.movement_type, str(m.quantity), f"{m.document_type} #{m.document_id or '-'}", m.reason])
        page_count = max(1, math.ceil(self._total / self.PAGE_SIZE))
        self.page_status.setText(f"Página {self._page} de {page_count} · {self._total:,} productos".replace(",", "."))
        self.prev_page.setEnabled(self._page > 1)
        self.next_page.setEnabled(self._page < page_count)

    def _view_inventory_image(self, row: int, column: int) -> None:
        if column != 0 or not (0 <= row < len(self._visible_inventory_rows)):
            return
        product = self._visible_inventory_rows[row]
        full_product = self.service.get_product(product["id"])
        if full_product:
            ProductImageDialog(full_product.name, full_product.image_data, full_product.image_path, self).exec()

    def _previous_page(self):
        if self._page > 1:
            self._page -= 1
            self.refresh()

    def _next_page(self):
        page_count = max(1, math.ceil(self._total / self.PAGE_SIZE))
        if self._page < page_count:
            self._page += 1
            self.refresh()

    def adjust_stock(self):
        products = self.service.list_products(active_only=True)
        if not products:
            show_error(self, "Crea un producto antes de ajustar inventario.")
            return
        dlg = StockAdjustmentDialog(products, self)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            pid, qty, reason, notes = dlg.values()
            self.service.adjust_stock(product_id=pid, quantity=qty, reason=reason, notes=notes)
            self._page = 1
            self.refresh()
            show_info(self, "Ajuste de inventario registrado y auditado.")
        except Exception as exc:
            show_error(self, str(exc))
