from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.exceptions import DomainError
from app.services import (
    DELIVERY_STATUSES,
    SHIPPING_CUSTOMER_DIRECT,
    SHIPPING_CUSTOMER_ORDER,
    SHIPPING_PAYER_LABELS,
    SHIPPING_STORE,
    StoreService,
)
from .product_image_widgets import ProductImageDialog, product_pixmap
from .ui_helpers import (
    add_row,
    add_table_columns,
    confirm,
    fit_table,
    fmt_money,
    make_lineedit,
    make_money_edit,
    parse_money,
    show_error,
    show_info,
)


SHIPPING_HINTS = {
    SHIPPING_STORE: "Tecnocity paga el domicilio: el costo real se descuenta de la ganancia y no se cobra al cliente.",
    SHIPPING_CUSTOMER_ORDER: "El cliente paga el domicilio dentro de la venta: se suma al total y el costo real se descuenta de la ganancia.",
    SHIPPING_CUSTOMER_DIRECT: "El cliente paga directo al domiciliario: no cambia el total ni la ganancia de Tecnocity.",
}


class ReturnDialog(QDialog):
    def __init__(self, sale, parent=None):
        super().__init__(parent)
        self.sale = sale
        self.setWindowTitle(f"Devolver {sale.number}")
        self.setMinimumWidth(650)
        layout = QVBoxLayout(self)
        label = QLabel("Indica cuántas unidades regresan al inventario. La aplicación reconstruye el costo FIFO original.")
        label.setWordWrap(True)
        label.setObjectName("mutedText")
        layout.addWidget(label)

        self.qty_edits: dict[int, QSpinBox] = {}
        grid = QGridLayout()
        grid.addWidget(QLabel("Producto"), 0, 0)
        grid.addWidget(QLabel("Vendido"), 0, 1)
        grid.addWidget(QLabel("Devuelto"), 0, 2)
        grid.addWidget(QLabel("A devolver"), 0, 3)
        r = 1
        for item in sale.items:
            remaining = item.quantity - item.returned_quantity
            if remaining <= 0:
                continue
            grid.addWidget(QLabel(f"{item.sku_snapshot} · {item.product_name_snapshot}"), r, 0)
            grid.addWidget(QLabel(str(item.quantity)), r, 1)
            grid.addWidget(QLabel(str(item.returned_quantity)), r, 2)
            spin = QSpinBox()
            spin.setRange(0, remaining)
            spin.setValue(0)
            grid.addWidget(spin, r, 3)
            self.qty_edits[item.id] = spin
            r += 1
        layout.addLayout(grid)

        form = QFormLayout()
        self.reason = make_lineedit("Ej.: Producto defectuoso / cliente devuelve pedido")
        self.refund_shipping = QCheckBox("Reembolsar también el domicilio cobrado al cliente")
        self.notes = make_lineedit("Observación opcional")
        form.addRow("Motivo", self.reason)
        form.addRow("Domicilio", self.refund_shipping)
        form.addRow("Observación", self.notes)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        return {
            "items": [
                {"sale_item_id": item_id, "quantity": spin.value()}
                for item_id, spin in self.qty_edits.items()
                if spin.value() > 0
            ],
            "reason": self.reason.text(),
            "refund_shipping": self.refund_shipping.isChecked(),
            "notes": self.notes.text(),
        }


class CancelDialog(QDialog):
    def __init__(self, sale, parent=None):
        super().__init__(parent)
        self.sale = sale
        self.setWindowTitle(f"Cancelar {sale.number}")
        self.setMinimumWidth(520)
        form = QFormLayout(self)
        info = QLabel("La cancelación devuelve las unidades aún no devueltas al inventario y conserva el historial. Los gastos ya incurridos no se borran.")
        info.setWordWrap(True)
        info.setObjectName("mutedText")
        form.addRow(info)
        self.reason = make_lineedit("Motivo obligatorio")
        self.refund_shipping = QCheckBox("Reembolsar el domicilio cobrado al cliente")
        self.refund_shipping.setChecked(True)
        self.notes = make_lineedit("Observación opcional")
        form.addRow("Motivo", self.reason)
        form.addRow("Domicilio", self.refund_shipping)
        form.addRow("Observación", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        return {"reason": self.reason.text(), "refund_shipping": self.refund_shipping.isChecked(), "notes": self.notes.text()}


class DeliveryDialog(QDialog):
    def __init__(self, current: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Estado de entrega")
        form = QFormLayout(self)
        self.status = QComboBox()
        self.status.addItems(list(DELIVERY_STATUSES))
        if current in DELIVERY_STATUSES:
            self.status.setCurrentText(current)
        form.addRow("Estado", self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class SaleDetailDialog(QDialog):
    def __init__(self, service: StoreService, sale_id: int, parent=None):
        super().__init__(parent)
        self.service = service
        self.sale_id = sale_id
        sale = service.get_sale(sale_id)
        if not sale:
            raise ValueError("Venta no encontrada.")
        self.sale = sale
        summary = service.sale_summary(sale_id)
        self.setWindowTitle(f"Detalle {sale.number}")
        self.setMinimumSize(820, 620)
        layout = QVBoxLayout(self)

        header = QGridLayout()
        fields = [
            ("Cliente", sale.customer_name or "No registrado"),
            ("Teléfono", sale.customer_phone or "—"),
            ("Estado", sale.status),
            ("Entrega", sale.delivery_status),
            ("Pago", sale.payment_method),
            ("Domicilio", SHIPPING_PAYER_LABELS.get(sale.shipping_payer, sale.shipping_payer)),
            ("Costo domicilio", fmt_money(sale.shipping_cost)),
            ("Cobro domicilio", fmt_money(sale.shipping_charge)),
            ("Total original", fmt_money(sale.total)),
            ("Total neto actual", fmt_money(summary["net_total"])),
            ("Costo mercancía actual", fmt_money(summary["current_cogs"])),
            ("Ganancia neta actual", fmt_money(summary["current_profit"])),
        ]
        for i, (label, value) in enumerate(fields):
            header.addWidget(QLabel(f"<b>{label}</b>"), i // 2, (i % 2) * 2)
            header.addWidget(QLabel(str(value)), i // 2, (i % 2) * 2 + 1)
        layout.addLayout(header)

        table = QTableWidget()
        add_table_columns(table, ["SKU", "Producto", "Cant.", "Dev.", "Precio", "Total", "Costo FIFO"])
        for item in sale.items:
            add_row(table, [
                item.sku_snapshot,
                item.product_name_snapshot,
                str(item.quantity),
                str(item.returned_quantity),
                fmt_money(item.unit_sale_price),
                fmt_money(item.line_total),
                fmt_money(item.cogs),
            ])
        table.setColumnWidth(0, 110)
        table.horizontalHeader().setStretchLastSection(False)
        layout.addWidget(table, 1)

        returns = QTableWidget()
        add_table_columns(returns, ["Fecha", "Motivo", "Reembolso", "Costo recuperado", "Impacto utilidad"])
        for ret in sale.returns:
            add_row(returns, [ret.return_date.strftime("%Y-%m-%d %H:%M"), ret.reason, fmt_money(ret.total_refunded), fmt_money(ret.cogs_returned), fmt_money(ret.profit_impact)])
        layout.addWidget(QLabel("Devoluciones / cancelaciones"))
        layout.addWidget(returns, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class CartPage(QWidget):
    mode = "purchase"

    def __init__(self, service: StoreService):
        super().__init__()
        self.service = service
        self.cart: list[dict] = []
        self._charge_manual = False
        self._ui_ready = False
        self._build_ui()
        self._ui_ready = True
        if self.mode == "sale":
            self._sync_shipping_mode()
        self.refresh_cart()
        self.refresh_products()
        self.refresh_history()

    def _build_ui(self) -> None:
        # Todo el contenido vive dentro de un área con scroll: en pantallas bajas
        # los formularios ya no se aplastan ni se solapan.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("pageContent")
        scroll.setWidget(content)
        outer.addWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)
        title = QLabel("Compras" if self.mode == "purchase" else "Ventas")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Registra compras e inversión y actualiza el inventario automáticamente."
            if self.mode == "purchase"
            else "Registra la venta completa, domicilio, cliente y pago; el costo FIFO se guarda automáticamente."
        )
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        product_box = QGroupBox("Detalle de la operación")
        product_layout = QGridLayout(product_box)
        product_layout.setHorizontalSpacing(10)
        product_layout.setVerticalSpacing(8)
        self.product = QComboBox()
        self.product.setMinimumWidth(340)
        self.product.currentIndexChanged.connect(self._sync_product_price)
        self.qty = QSpinBox()
        self.qty.setRange(1, 1_000_000)
        self.qty.setValue(1)
        self.price = make_money_edit()
        add_button = QPushButton("Agregar")
        add_button.setObjectName("secondaryButton")
        add_button.clicked.connect(self.add_line)
        product_layout.addWidget(QLabel("Producto"), 0, 0)
        product_layout.addWidget(self.product, 0, 1, 1, 3)
        product_layout.addWidget(QLabel("Cantidad"), 0, 4)
        product_layout.addWidget(self.qty, 0, 5)
        product_layout.addWidget(QLabel("Costo unit." if self.mode == "purchase" else "Precio venta"), 0, 6)
        product_layout.addWidget(self.price, 0, 7)
        product_layout.addWidget(add_button, 0, 8)

        image_row = QHBoxLayout()
        image_row.setSpacing(10)
        self.product_image_button = QPushButton("Sin imagen")
        self.product_image_button.setObjectName("secondaryButton")
        self.product_image_button.setFixedSize(82, 76)
        self.product_image_button.setIconSize(QSize(68, 62))
        self.product_image_button.setToolTip("Abrir la imagen del producto seleccionado")
        self.product_image_button.clicked.connect(self.view_selected_product_image)
        image_row.addWidget(self.product_image_button)
        self.product_image_info = QLabel("Selecciona un producto para ver su imagen.")
        self.product_image_info.setObjectName("hintText")
        self.product_image_info.setWordWrap(True)
        image_row.addWidget(self.product_image_info, 1)
        if self.mode == "purchase":
            self.new_product_button = QPushButton("+ Nuevo producto")
            self.new_product_button.setObjectName("secondaryButton")
            self.new_product_button.setToolTip("Crear un producto y asignarle su imagen sin salir de Compras")
            self.new_product_button.clicked.connect(self.create_product_from_purchase)
            image_row.addWidget(self.new_product_button)
        product_layout.addLayout(image_row, 1, 0, 1, 9)
        layout.addWidget(product_box)

        self.table = QTableWidget()
        add_table_columns(self.table, ["Producto", "Cantidad", "Precio", "Total", "Acción"])
        self.table.cellDoubleClicked.connect(self.remove_line)
        fit_table(self.table, stretch_column=0)
        self.table.setMinimumHeight(150)
        layout.addWidget(self.table, 1)

        info_row = QHBoxLayout()
        if self.mode == "purchase":
            self._build_purchase_fields(info_row)
        else:
            self._build_sale_fields(info_row)
        layout.addLayout(info_row)

        action_row = QHBoxLayout()
        self.total_label = QLabel("Total: $ 0,00")
        self.total_label.setObjectName("totalLabel")
        action_row.addWidget(self.total_label)
        if self.mode == "sale":
            self.cogs_label = QLabel("Costo FIFO: $ 0,00")
            self.cogs_label.setObjectName("summaryLabel")
            self.profit_label = QLabel("Ganancia estimada: $ 0,00")
            self.profit_label.setObjectName("profitLabel")
            action_row.addSpacing(18)
            action_row.addWidget(self.cogs_label)
            action_row.addSpacing(18)
            action_row.addWidget(self.profit_label)
        action_row.addStretch()
        self.save_button = QPushButton("REGISTRAR COMPRA" if self.mode == "purchase" else "REGISTRAR VENTA")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self.save)
        action_row.addWidget(self.save_button)
        layout.addLayout(action_row)
        self.validation_label = QLabel("")
        self.validation_label.setObjectName("errorText")
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)

        history_title = QLabel("Operaciones recientes")
        history_title.setObjectName("sectionLabel")
        layout.addWidget(history_title)
        self.history = QTableWidget()
        if self.mode == "purchase":
            add_table_columns(self.history, ["Fecha", "Documento", "Subtotal", "Total", "Resultado"])
            fit_table(self.history, stretch_column=4)
        else:
            add_table_columns(self.history, ["Fecha", "Documento", "Total original", "Total neto", "Ganancia actual", "Estado", "Entrega"])
            fit_table(self.history, stretch_column=6)
            self.history.cellDoubleClicked.connect(lambda row, _column: self.view_sale(row))
        self.history.setMinimumHeight(170)
        layout.addWidget(self.history, 1)
        if self.mode == "sale":
            manage = QHBoxLayout()
            self.view_btn = QPushButton("Ver detalle")
            self.return_btn = QPushButton("Devolver")
            self.cancel_btn = QPushButton("Cancelar venta")
            self.delivery_btn = QPushButton("Estado entrega")
            for btn in (self.view_btn, self.return_btn, self.cancel_btn, self.delivery_btn):
                btn.setObjectName("secondaryButton")
                manage.addWidget(btn)
            manage.addStretch()
            self.view_btn.clicked.connect(self.view_selected_sale)
            self.return_btn.clicked.connect(self.return_selected_sale)
            self.cancel_btn.clicked.connect(self.cancel_selected_sale)
            self.delivery_btn.clicked.connect(self.change_selected_delivery)
            layout.addLayout(manage)

    def _build_purchase_fields(self, parent_layout: QHBoxLayout) -> None:
        box = QGroupBox("Datos de compra")
        form = QFormLayout(box)
        self.supplier = make_lineedit("Proveedor")
        self.shipping = make_money_edit()
        self.other = make_money_edit()
        self.notes = make_lineedit("Observación opcional")
        self.shipping.textChanged.connect(self.refresh_cart)
        self.other.textChanged.connect(self.refresh_cart)
        form.addRow("Proveedor", self.supplier)
        form.addRow("Transporte / envío", self.shipping)
        form.addRow("Otros gastos", self.other)
        form.addRow("Observación", self.notes)
        parent_layout.addWidget(box, 1)

    def _build_sale_fields(self, parent_layout: QHBoxLayout) -> None:
        customer_box = QGroupBox("Cliente y entrega")
        customer_form = QFormLayout(customer_box)
        self.customer_name = make_lineedit("Nombre opcional")
        self.customer_phone = make_lineedit("Teléfono")
        self.customer_address = make_lineedit("Dirección de entrega")
        self.delivery = QComboBox()
        self.delivery.addItems(list(DELIVERY_STATUSES))
        customer_form.addRow("Cliente", self.customer_name)
        customer_form.addRow("Teléfono", self.customer_phone)
        customer_form.addRow("Dirección", self.customer_address)
        customer_form.addRow("Estado entrega", self.delivery)

        sale_box = QGroupBox("Pago, descuento y domicilio")
        grid = QGridLayout(sale_box)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.discount = make_money_edit()
        self.shipping_payer = QComboBox()
        for key, label in SHIPPING_PAYER_LABELS.items():
            self.shipping_payer.addItem(label, key)
        self.shipping_cost = make_money_edit()
        self.shipping_charge = make_money_edit()
        self.commission = make_money_edit()
        self.other = make_money_edit()
        self.payment = QComboBox()
        self.payment.addItems(["Efectivo", "Transferencia", "Tarjeta", "Nequi/Daviplata", "Otro"])
        self.notes = make_lineedit("Observación opcional")
        self.shipping_hint = QLabel("")
        self.shipping_hint.setObjectName("hintText")
        self.shipping_hint.setWordWrap(True)

        def field(text: str, widget, row: int, col: int, span: int = 1) -> None:
            label = QLabel(text)
            label.setObjectName("fieldLabel")
            grid.addWidget(label, row, col, 1, span)
            grid.addWidget(widget, row + 1, col, 1, span)

        field("Descuento global", self.discount, 0, 0)
        field("Método de pago", self.payment, 0, 1)
        field("Quién paga el domicilio", self.shipping_payer, 2, 0, 2)
        grid.addWidget(self.shipping_hint, 4, 0, 1, 2)
        field("Costo real del domicilio", self.shipping_cost, 5, 0)
        field("Cobro del domicilio al cliente", self.shipping_charge, 5, 1)
        field("Comisión", self.commission, 7, 0)
        field("Otros gastos", self.other, 7, 1)
        field("Observación", self.notes, 9, 0, 2)

        self.shipping_payer.currentIndexChanged.connect(self._sync_shipping_mode)
        self.shipping_cost.textChanged.connect(self._maybe_copy_shipping_cost)
        self.shipping_charge.textEdited.connect(self._mark_charge_manual)
        self.shipping_charge.textChanged.connect(self.refresh_cart)
        self.discount.textChanged.connect(self.refresh_cart)
        self.commission.textChanged.connect(self.refresh_cart)
        self.other.textChanged.connect(self.refresh_cart)
        parent_layout.addWidget(customer_box, 1)
        parent_layout.addWidget(sale_box, 1)

    def refresh_products(self, select_product_id: int | None = None) -> None:
        self.product.blockSignals(True)
        current = self.product.currentData()
        self.product.clear()
        for p in self.service.list_products(active_only=True):
            label = f"{p.sku} · {p.name} · stock {p.stock_current}"
            self.product.addItem(label, p.id)
        target_id = select_product_id if select_product_id is not None else current
        if target_id is not None:
            idx = self.product.findData(target_id)
            if idx >= 0:
                self.product.setCurrentIndex(idx)
        self.product.blockSignals(False)
        self._sync_product_price()

    def _sync_product_price(self, *_args) -> None:
        pid = self.product.currentData()
        if not pid:
            self.price.clear()
            self.product_image_button.setIcon(QIcon())
            self.product_image_button.setText("Sin imagen")
            self.product_image_info.setText("Selecciona un producto para ver su imagen.")
            return
        product = self.service.get_product(pid)
        if product:
            if self.mode == "sale":
                self.price.setText(str(product.sale_price).replace(".", ","))
            elif not self.price.text().strip() or self.price.text() == "0,00":
                self.price.setText("0,00")
            pixmap = product_pixmap(product, QSize(68, 62))
            if pixmap.isNull():
                self.product_image_button.setIcon(QIcon())
                self.product_image_button.setText("Sin imagen")
            else:
                self.product_image_button.setText("")
                self.product_image_button.setIcon(QIcon(pixmap))
            self.product_image_info.setText(
                f"{product.name} · {product.brand or 'Sin marca'} · {product.category or 'General'}"
                + (" · Clic en la imagen para ampliar" if not pixmap.isNull() else " · Aún sin imagen")
            )

    def view_selected_product_image(self) -> None:
        pid = self.product.currentData()
        if not pid:
            show_error(self, "Selecciona un producto para consultar su imagen.")
            return
        product = self.service.get_product(pid)
        if product:
            ProductImageDialog(product.name, product.image_data, product.image_path, self).exec()

    def create_product_from_purchase(self) -> None:
        if self.mode != "purchase":
            return
        from .products_page import ProductDialog

        dialog = ProductDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            product = self.service.create_product(**dialog.values())
            self.refresh_products(select_product_id=product.id)
            # Purchase cost is distinct from the catalogue sale price and must be entered by the user.
            self.price.setText("0,00")
            self.qty.setValue(1)
            show_info(self, f"Producto {product.name} creado. Completa el costo de compra y registra la entrada al inventario.")
        except Exception as exc:
            show_error(self, str(exc))

    def add_line(self) -> None:
        pid = self.product.currentData()
        if not pid:
            show_error(self, "Selecciona un producto.")
            return
        product = self.service.get_product(pid)
        if not product:
            show_error(self, "El producto seleccionado ya no existe.")
            return
        try:
            price = parse_money(self.price.text())
        except ValueError as exc:
            show_error(self, str(exc))
            return
        qty = self.qty.value()
        if price < 0:
            show_error(self, "El importe no puede ser negativo.")
            return
        existing = sum(line["quantity"] for line in self.cart if line["product_id"] == pid)
        if self.mode == "sale" and existing + qty > product.stock_current:
            show_error(self, f"Stock insuficiente. Disponible: {product.stock_current}; ya agregaste {existing}.")
            return
        # Mantén una sola línea por producto para que la devolución y auditoría sean claras.
        for line in self.cart:
            if line["product_id"] == pid:
                line["quantity"] += qty
                line["unit_price"] = price
                break
        else:
            self.cart.append({"product_id": pid, "name": product.name, "quantity": qty, "unit_price": price})
        self.refresh_cart()
        if self.mode == "sale":
            self._sync_product_price()

    def remove_line(self, row: int, _column: int = 0) -> None:
        if 0 <= row < len(self.cart):
            self.cart.pop(row)
            self.refresh_cart()

    def _sync_shipping_mode(self, *_args) -> None:
        """Habilita solo los campos de domicilio que aplican a la modalidad elegida."""
        mode = self.shipping_payer.currentData() if hasattr(self, "shipping_payer") else SHIPPING_STORE
        customer_pays_in_order = mode == SHIPPING_CUSTOMER_ORDER
        customer_pays_courier = mode == SHIPPING_CUSTOMER_DIRECT
        # Si el cliente paga directo al domiciliario, Tecnocity no tiene costo de domicilio.
        self.shipping_cost.setEnabled(not customer_pays_courier)
        self.shipping_charge.setEnabled(customer_pays_in_order)
        if customer_pays_courier:
            self.shipping_cost.setText("0,00")
        if not customer_pays_in_order:
            self._charge_manual = False
            self.shipping_charge.setText("0,00")
        elif not self._charge_manual:
            self.shipping_charge.setText(self.shipping_cost.text() or "0,00")
        self.shipping_hint.setText(SHIPPING_HINTS.get(mode, ""))
        self.refresh_cart()

    def _mark_charge_manual(self, *_args) -> None:
        # Solo se dispara cuando el usuario escribe en el cobro; a partir de ahí ya no se copia el costo.
        self._charge_manual = True

    def _maybe_copy_shipping_cost(self, *_args) -> None:
        if self.shipping_payer.currentData() == SHIPPING_CUSTOMER_ORDER and not self._charge_manual:
            self.shipping_charge.setText(self.shipping_cost.text())
        self.refresh_cart()

    def refresh_cart(self, *_args) -> None:
        if not getattr(self, "_ui_ready", False):
            return
        self.table.setRowCount(0)
        try:
            if self.mode == "purchase":
                preview = self.service.preview_purchase(
                    items=[{"product_id": x["product_id"], "quantity": x["quantity"], "unit_cost": x["unit_price"]} for x in self.cart],
                    shipping_cost=parse_money(self.shipping.text()),
                    other_cost=parse_money(self.other.text()),
                )
            else:
                preview = self.service.preview_sale(
                    items=[{"product_id": x["product_id"], "quantity": x["quantity"], "unit_sale_price": x["unit_price"]} for x in self.cart],
                    discount=parse_money(self.discount.text()),
                    shipping_cost=parse_money(self.shipping_cost.text()),
                    shipping_charge=parse_money(self.shipping_charge.text()),
                    shipping_payer=self.shipping_payer.currentData(),
                    commission=parse_money(self.commission.text()),
                    other_cost=parse_money(self.other.text()),
                )
            for line, line_total_value in zip(self.cart, preview["line_totals"]):
                add_row(self.table, [line["name"], str(line["quantity"]), fmt_money(line["unit_price"]), fmt_money(line_total_value), "Doble clic para quitar"])
            self.total_label.setText(f"Total: {fmt_money(preview['total'])}")
            self.validation_label.setText("")
            if self.mode == "sale":
                self.cogs_label.setText(f"Costo FIFO: {fmt_money(preview['cogs'])}")
                self.profit_label.setText(f"Ganancia estimada: {fmt_money(preview['net_profit'])}")
        except (DomainError, ValueError) as exc:
            # Mientras el usuario edita no interrumpimos con diálogos: el motivo se muestra en línea.
            self.validation_label.setText(str(exc))
            self.total_label.setText("Total: $ 0,00")
            if self.mode == "sale":
                self.cogs_label.setText("Costo FIFO: $ 0,00")
                self.profit_label.setText("Ganancia estimada: $ 0,00")
        except Exception:
            self.validation_label.setText("No se pudo calcular el resumen de la operación.")
            self.total_label.setText("Total: $ 0,00")
            if self.mode == "sale":
                self.cogs_label.setText("Costo FIFO: $ 0,00")
                self.profit_label.setText("Ganancia estimada: $ 0,00")

    def save(self) -> None:
        if not self.cart:
            show_error(self, "Agrega al menos un producto al detalle.")
            return
        try:
            if self.mode == "purchase":
                try:
                    preview = self.service.preview_purchase(
                        items=[{"product_id": x["product_id"], "quantity": x["quantity"], "unit_cost": x["unit_price"]} for x in self.cart],
                        shipping_cost=parse_money(self.shipping.text()),
                        other_cost=parse_money(self.other.text()),
                    )
                    confirm_message = f"¿Registrar compra por {fmt_money(preview['total'])}?"
                except Exception as exc:
                    show_error(self, str(exc))
                    return
                if not confirm(self, "Confirmar compra", confirm_message):
                    return
                purchase = self.service.register_purchase(
                    supplier=self.supplier.text(),
                    items=[{"product_id": x["product_id"], "quantity": x["quantity"], "unit_cost": x["unit_price"]} for x in self.cart],
                    shipping_cost=parse_money(self.shipping.text()),
                    other_cost=parse_money(self.other.text()),
                    notes=self.notes.text(),
                )
                message = f"Compra {purchase.number} registrada por {fmt_money(purchase.total)}."
            else:
                preview = self.service.preview_sale(
                    items=[{"product_id": x["product_id"], "quantity": x["quantity"], "unit_sale_price": x["unit_price"]} for x in self.cart],
                    discount=parse_money(self.discount.text()),
                    shipping_cost=parse_money(self.shipping_cost.text()),
                    shipping_charge=parse_money(self.shipping_charge.text()),
                    shipping_payer=self.shipping_payer.currentData(),
                    commission=parse_money(self.commission.text()),
                    other_cost=parse_money(self.other.text()),
                )
                if not confirm(self, "Confirmar venta", f"¿Registrar venta por {fmt_money(preview['total'])} con ganancia estimada de {fmt_money(preview['net_profit'])}?"):
                    return
                sale = self.service.register_sale(
                    items=[{"product_id": x["product_id"], "quantity": x["quantity"], "unit_sale_price": x["unit_price"]} for x in self.cart],
                    discount=parse_money(self.discount.text()),
                    shipping_cost=parse_money(self.shipping_cost.text()),
                    shipping_charge=parse_money(self.shipping_charge.text()),
                    shipping_payer=self.shipping_payer.currentData(),
                    commission=parse_money(self.commission.text()),
                    other_cost=parse_money(self.other.text()),
                    payment_method=self.payment.currentText(),
                    notes=self.notes.text(),
                    customer_name=self.customer_name.text(),
                    customer_phone=self.customer_phone.text(),
                    customer_address=self.customer_address.text(),
                    delivery_status=self.delivery.currentText(),
                )
                shipping_note = SHIPPING_PAYER_LABELS.get(sale.shipping_payer, sale.shipping_payer)
                message = f"Venta {sale.number} registrada. Total cobrado: {fmt_money(sale.total)}. Ganancia inicial: {fmt_money(sale.net_profit)}. {shipping_note}."

            self.cart.clear()
            self._reset_optional_fields()
            self.refresh_cart()
            self.refresh_products()
            self.refresh_history()
            main_window = self.window()
            if hasattr(main_window, "refresh_all"):
                main_window.refresh_all()
            show_info(self, message)
        except Exception as exc:
            show_error(self, str(exc))

    def _reset_optional_fields(self) -> None:
        if self.mode == "purchase":
            self.shipping.setText("0,00")
            self.other.setText("0,00")
            self.supplier.clear()
            self.notes.clear()
        else:
            self._charge_manual = False
            self.discount.setText("0,00")
            self.shipping_cost.setText("0,00")
            self.shipping_charge.setText("0,00")
            self.shipping_payer.setCurrentIndex(0)
            self._sync_shipping_mode()
            self.commission.setText("0,00")
            self.other.setText("0,00")
            self.payment.setCurrentIndex(0)
            self.delivery.setCurrentIndex(0)
            self.customer_name.clear()
            self.customer_phone.clear()
            self.customer_address.clear()
            self.notes.clear()

    def refresh_history(self) -> None:
        if not hasattr(self, "history"):
            return
        self.history.setRowCount(0)
        if self.mode == "purchase":
            for record in self.service.purchases():
                add_row(self.history, [record.purchase_date.strftime("%Y-%m-%d"), record.number, fmt_money(record.subtotal), fmt_money(record.total), "REGISTRADA"])
        else:
            for record in self.service.sales():
                summary = self.service.sale_summary(record.id)
                add_row(self.history, [record.sale_date.strftime("%Y-%m-%d"), record.number, fmt_money(record.total), fmt_money(summary["net_total"]), fmt_money(summary["current_profit"]), record.status, record.delivery_status])

    def _selected_sale(self):
        row = self.history.currentRow()
        if row < 0 or self.mode != "sale":
            show_error(self, "Selecciona una venta del historial.")
            return None
        number_item = self.history.item(row, 1)
        if not number_item:
            return None
        sale = self.service.get_sale_by_number(number_item.text())
        if not sale:
            show_error(self, "La venta seleccionada ya no existe.")
        return sale

    def view_sale(self, row: int) -> None:
        self.history.selectRow(row)
        self.view_selected_sale()

    def view_selected_sale(self) -> None:
        sale = self._selected_sale()
        if not sale:
            return
        try:
            dlg = SaleDetailDialog(self.service, sale.id, self)
            dlg.exec()
        except Exception as exc:
            show_error(self, str(exc))

    def return_selected_sale(self) -> None:
        sale = self._selected_sale()
        if not sale or sale.status in {"CANCELADA", "DEVUELTA_COMPLETA"}:
            return
        dlg = ReturnDialog(sale, self)
        if dlg.exec() != QDialog.Accepted:
            return
        values = dlg.values()
        if not values["items"]:
            show_error(self, "Selecciona al menos una unidad para devolver.")
            return
        try:
            ret = self.service.return_sale(sale_id=sale.id, **values)
            self.refresh_history()
            self.refresh_products()
            self.window().refresh_all()
            show_info(self, f"Devolución registrada. Reembolso: {fmt_money(ret.total_refunded)}.")
        except Exception as exc:
            show_error(self, str(exc))

    def cancel_selected_sale(self) -> None:
        sale = self._selected_sale()
        if not sale or sale.status in {"CANCELADA", "DEVUELTA_COMPLETA"}:
            return
        dlg = CancelDialog(sale, self)
        if dlg.exec() != QDialog.Accepted:
            return
        values = dlg.values()
        if not values["reason"].strip():
            show_error(self, "El motivo de cancelación es obligatorio.")
            return
        if not confirm(self, "Confirmar cancelación", f"¿Confirmas cancelar la venta {sale.number}? Esta acción conserva el historial y devuelve el inventario pendiente."):
            return
        try:
            self.service.cancel_sale(sale_id=sale.id, **values)
            self.refresh_history()
            self.refresh_products()
            self.window().refresh_all()
            show_info(self, f"Venta {sale.number} cancelada correctamente.")
        except Exception as exc:
            show_error(self, str(exc))

    def change_selected_delivery(self) -> None:
        sale = self._selected_sale()
        if not sale:
            return
        dlg = DeliveryDialog(sale.delivery_status, self)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_delivery_status(sale.id, dlg.status.currentText())
            self.refresh_history()
            show_info(self, "Estado de entrega actualizado.")
        except Exception as exc:
            show_error(self, str(exc))


class PurchasesPage(CartPage):
    mode = "purchase"


class SalesPage(CartPage):
    mode = "sale"
