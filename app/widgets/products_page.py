from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from PySide6.QtCore import QDate, QSignalBlocker, QTimer, Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QDateEdit,
)

from app.services import ProductFilter, StoreService
from .ui_helpers import add_row, add_table_columns, fmt_money, make_lineedit, parse_money, show_error, show_info
from .product_image_widgets import ProductImageDialog, load_product_pixmap, product_pixmap
from app.utils.product_images import encode_product_image, encode_product_thumbnail


class ProductDialog(QDialog):
    """Product editor with an optional image optimized for storage in SQLite."""

    def __init__(self, parent=None, product=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle("Editar producto" if product else "Nuevo producto")
        self.setMinimumWidth(540)
        self._image_changed = False
        self._image_data: bytes | None = bytes(product.image_data) if product and product.image_data else None
        self._image_thumbnail_data: bytes | None = bytes(product.image_thumbnail_data) if product and product.image_thumbnail_data else None
        self._legacy_image_path = str(product.image_path or "") if product else ""

        form = QFormLayout(self)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setContentsMargins(20, 18, 20, 18)
        form.setSpacing(10)
        self.sku = make_lineedit("TEC-001")
        self.name = make_lineedit("Nombre del producto")
        self.category = make_lineedit("General")
        self.brand = make_lineedit("Opcional")
        self.price = make_lineedit("0.00")
        self.stock_min = QSpinBox()
        self.stock_min.setRange(0, 1_000_000)
        self.description = make_lineedit("Descripción corta")
        if product:
            self.sku.setText(product.sku)
            self.name.setText(product.name)
            self.category.setText(product.category)
            self.brand.setText(product.brand)
            self.price.setText(str(product.sale_price))
            self.stock_min.setValue(product.stock_min)
            self.description.setText(product.description)

        form.addRow("SKU", self.sku)
        form.addRow("Nombre", self.name)
        form.addRow("Categoría", self.category)
        form.addRow("Marca", self.brand)
        form.addRow("Precio venta", self.price)
        form.addRow("Stock mínimo", self.stock_min)
        form.addRow("Descripción", self.description)

        image_row = QHBoxLayout()
        image_row.setSpacing(12)
        self.image_preview = QLabel("Sin imagen")
        self.image_preview.setObjectName("productImagePreview")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.image_preview.setFixedSize(132, 118)
        image_row.addWidget(self.image_preview, 0, Qt.AlignmentFlag.AlignVCenter)

        image_actions = QVBoxLayout()
        self.select_image_button = QPushButton("Seleccionar imagen…")
        self.select_image_button.setObjectName("secondaryButton")
        self.select_image_button.clicked.connect(self.select_image)
        self.view_image_button = QPushButton("Ver imagen")
        self.view_image_button.setObjectName("secondaryButton")
        self.view_image_button.clicked.connect(self.view_image)
        self.remove_image_button = QPushButton("Quitar imagen")
        self.remove_image_button.setObjectName("secondaryButton")
        self.remove_image_button.clicked.connect(self.remove_image)
        for button in (self.select_image_button, self.view_image_button, self.remove_image_button):
            image_actions.addWidget(button)
        image_actions.addStretch(1)
        image_row.addLayout(image_actions, 1)
        image_widget = QWidget()
        image_widget.setLayout(image_row)
        form.addRow("Imagen del producto", image_widget)
        hint = QLabel("Opcional · JPG, PNG, WEBP, BMP o GIF. Se optimiza y queda incluida en los respaldos.")
        hint.setObjectName("hintText")
        hint.setWordWrap(True)
        form.addRow("", hint)
        self._render_image_preview()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _effective_image_path(self) -> str:
        if self._image_changed:
            return ""
        return self._legacy_image_path

    def _render_image_preview(self) -> None:
        pixmap = load_product_pixmap(self._image_data, self._effective_image_path(), QSize(120, 106))
        if pixmap.isNull():
            self.image_preview.clear()
            self.image_preview.setText("Sin imagen")
            self.view_image_button.setEnabled(False)
        else:
            self.image_preview.setPixmap(pixmap)
            self.image_preview.setText("")
            self.view_image_button.setEnabled(True)

    def select_image(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar imagen del producto",
            "",
            "Imágenes (*.jpg *.jpeg *.png *.webp *.bmp *.gif)",
        )
        if not source:
            return
        try:
            data = encode_product_image(source)
        except Exception as exc:
            show_error(self, str(exc))
            return
        try:
            thumbnail = encode_product_thumbnail(data)
        except Exception as exc:
            show_error(self, str(exc))
            return
        self._image_data = data
        self._image_thumbnail_data = thumbnail
        self._legacy_image_path = ""
        self._image_changed = True
        self._render_image_preview()

    def remove_image(self) -> None:
        self._image_data = None
        self._image_thumbnail_data = None
        self._legacy_image_path = ""
        self._image_changed = True
        self._render_image_preview()

    def view_image(self) -> None:
        dlg = ProductImageDialog(
            self.name.text().strip() or "Producto",
            image_data=self._image_data,
            image_path=self._effective_image_path(),
            parent=self,
        )
        dlg.exec()

    def values(self):
        result = dict(
            sku=self.sku.text(),
            name=self.name.text(),
            category=self.category.text(),
            brand=self.brand.text(),
            sale_price=parse_money(self.price.text()),
            stock_min=self.stock_min.value(),
            description=self.description.text(),
        )
        # For edits, omit image_data unless the user deliberately changed it.
        # This keeps an existing image intact when other product fields change.
        if self.product is None or self._image_changed:
            result["image_data"] = self._image_data
            result["image_thumbnail_data"] = self._image_thumbnail_data
            result["image_path"] = self._effective_image_path()
        return result


class ProductsPage(QWidget):
    """Professional catalogue screen with server-side advanced filtering."""

    SORT_OPTIONS = [
        ("ID", "id"),
        ("SKU", "sku"),
        ("Nombre", "name"),
        ("Categoría", "category"),
        ("Marca", "brand"),
        ("Precio de venta", "sale_price"),
        ("Stock actual", "stock_current"),
        ("Stock mínimo", "stock_min"),
        ("Fecha de registro", "created_at"),
    ]

    def __init__(self, service: StoreService):
        super().__init__()
        self.service = service
        self._building_filters = False
        self._page = 1
        self._page_size = 100
        self._total_results = 0
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self.refresh)
        self._build_ui()
        self._load_filter_options()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 30)
        layout.setSpacing(14)

        head = QHBoxLayout()
        title = QVBoxLayout()
        t = QLabel("Productos")
        t.setObjectName("pageTitle")
        s = QLabel("Catálogo profesional con búsqueda y filtros avanzados.")
        s.setObjectName("pageSubtitle")
        title.addWidget(t); title.addWidget(s); head.addLayout(title); head.addStretch()
        new = QPushButton("+ Nuevo producto")
        new.setObjectName("primaryButton")
        new.clicked.connect(self.new_product)
        head.addWidget(new)
        layout.addLayout(head)

        self.filters_group = QGroupBox("Filtros avanzados")
        self.filters_group.setObjectName("productFilters")
        filter_grid = QGridLayout(self.filters_group)
        filter_grid.setHorizontalSpacing(10)
        filter_grid.setVerticalSpacing(8)
        filter_grid.setContentsMargins(14, 18, 14, 12)

        self.search = QLineEdit()
        self.search.setObjectName("productSearch")
        self.search.setPlaceholderText("Buscar por ID, SKU, nombre, categoría, marca o descripción...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._schedule_search)
        filter_grid.addWidget(QLabel("Búsqueda"), 0, 0)
        filter_grid.addWidget(self.search, 0, 1, 1, 3)

        self.category = QComboBox()
        self.category.setObjectName("productFilter")
        self.category.addItem("Todas las categorías", None)
        self.category.currentIndexChanged.connect(self._on_filter_changed)
        filter_grid.addWidget(QLabel("Categoría"), 0, 4)
        filter_grid.addWidget(self.category, 0, 5)

        self.brand = QComboBox()
        self.brand.setObjectName("productFilter")
        self.brand.addItem("Todas las marcas", None)
        self.brand.currentIndexChanged.connect(self._on_filter_changed)
        filter_grid.addWidget(QLabel("Marca"), 0, 6)
        filter_grid.addWidget(self.brand, 0, 7)

        self.status = QComboBox()
        self.status.setObjectName("productFilter")
        self.status.addItems(["Todos", "Activos", "Inactivos"])
        self.status.currentIndexChanged.connect(self._on_filter_changed)
        filter_grid.addWidget(QLabel("Estado"), 1, 0)
        filter_grid.addWidget(self.status, 1, 1)

        self.stock_status = QComboBox()
        self.stock_status.setObjectName("productFilter")
        self.stock_status.addItem("Todo el stock", "all")
        self.stock_status.addItem("Con stock", "in_stock")
        self.stock_status.addItem("Stock bajo", "low")
        self.stock_status.addItem("Agotados", "out")
        self.stock_status.currentIndexChanged.connect(self._on_filter_changed)
        filter_grid.addWidget(QLabel("Estado de stock"), 1, 2)
        filter_grid.addWidget(self.stock_status, 1, 3)

        self.id_exact = self._make_spin()
        self.id_min = self._make_spin()
        self.id_max = self._make_spin()
        for widget in (self.id_exact, self.id_min, self.id_max):
            widget.valueChanged.connect(self._on_filter_changed)
        filter_grid.addWidget(QLabel("ID exacto"), 1, 4)
        filter_grid.addWidget(self.id_exact, 1, 5)
        filter_grid.addWidget(QLabel("ID desde"), 1, 6)
        filter_grid.addWidget(self.id_min, 1, 7)

        self.price_min = QLineEdit()
        self.price_min.setObjectName("productFilter")
        self.price_min.setPlaceholderText("0,00")
        self.price_min.setClearButtonEnabled(True)
        self.price_max = QLineEdit()
        self.price_max.setObjectName("productFilter")
        self.price_max.setPlaceholderText("0,00")
        self.price_max.setClearButtonEnabled(True)
        self.price_min.editingFinished.connect(self._reset_and_refresh)
        self.price_max.editingFinished.connect(self._reset_and_refresh)
        filter_grid.addWidget(QLabel("Precio desde"), 2, 0)
        filter_grid.addWidget(self.price_min, 2, 1)
        filter_grid.addWidget(QLabel("Precio hasta"), 2, 2)
        filter_grid.addWidget(self.price_max, 2, 3)
        filter_grid.addWidget(QLabel("ID hasta"), 2, 4)
        filter_grid.addWidget(self.id_max, 2, 5)

        self.created_preset = QComboBox()
        self.created_preset.setObjectName("productFilter")
        self.created_preset.addItem("Cualquier fecha", "all")
        self.created_preset.addItem("Últimos 7 días", "7")
        self.created_preset.addItem("Últimos 30 días", "30")
        self.created_preset.addItem("Últimos 90 días", "90")
        self.created_preset.addItem("Este año", "year")
        self.created_preset.currentIndexChanged.connect(self._on_filter_changed)
        filter_grid.addWidget(QLabel("Registro"), 2, 6)
        filter_grid.addWidget(self.created_preset, 2, 7)

        self.sort_by = QComboBox()
        self.sort_by.setObjectName("productFilter")
        for label, value in self.SORT_OPTIONS:
            self.sort_by.addItem(label, value)
        self.sort_by.setCurrentIndex(0)
        self.sort_direction = QComboBox()
        self.sort_direction.setObjectName("productFilter")
        self.sort_direction.addItem("Ascendente ↑", "asc")
        self.sort_direction.addItem("Descendente ↓", "desc")
        self.sort_by.currentIndexChanged.connect(self._on_filter_changed)
        self.sort_direction.currentIndexChanged.connect(self._on_filter_changed)
        filter_grid.addWidget(QLabel("Ordenar por"), 3, 0)
        filter_grid.addWidget(self.sort_by, 3, 1)
        filter_grid.addWidget(QLabel("Dirección"), 3, 2)
        filter_grid.addWidget(self.sort_direction, 3, 3)

        self.clear_filters = QPushButton("Limpiar filtros")
        self.clear_filters.setObjectName("secondaryButton")
        self.clear_filters.clicked.connect(self.reset_filters)
        filter_grid.addWidget(self.clear_filters, 3, 4, 1, 2)

        self.filter_summary = QLabel()
        self.filter_summary.setObjectName("summaryLabel")
        filter_grid.addWidget(self.filter_summary, 3, 6, 1, 2)
        layout.addWidget(self.filters_group)

        self.table = QTableWidget()
        add_table_columns(self.table, ["Foto", "ID", "SKU", "Producto", "Categoría", "Marca", "Precio", "Stock", "Mín.", "Estado", "Acción"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 82)
        self.table.setColumnWidth(1, 56)
        self._visible_products = []
        self.table.cellDoubleClicked.connect(self.edit_product)
        self.table.cellClicked.connect(self._handle_click)
        self.table.setToolTip("Doble clic en un producto para editarlo.")
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

    @staticmethod
    def _make_spin() -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 2_147_483_647)
        spin.setSpecialValueText("Sin límite")
        spin.setValue(0)
        spin.setObjectName("productFilter")
        return spin

    def _load_filter_options(self):
        try:
            options = self.service.product_filter_options()
        except Exception as exc:
            show_error(self, str(exc))
            return
        current_category = self.category.currentData()
        current_brand = self.brand.currentData()
        with QSignalBlocker(self.category), QSignalBlocker(self.brand):
            self.category.clear()
            self.category.addItem("Todas las categorías", None)
            for value in options.get("categories", []):
                self.category.addItem(value, value)
            self.brand.clear()
            self.brand.addItem("Todas las marcas", None)
            for value in options.get("brands", []):
                self.brand.addItem(value, value)
            self._restore_combo_value(self.category, current_category)
            self._restore_combo_value(self.brand, current_brand)

    @staticmethod
    def _restore_combo_value(combo: QComboBox, value) -> None:
        if value is None:
            combo.setCurrentIndex(0)
            return
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    def _schedule_search(self, _text: str = ""):
        if self._building_filters:
            return
        self._page = 1
        self._search_timer.start()

    def _on_filter_changed(self, _index: int = -1):
        if self._building_filters:
            return
        self._page = 1
        self.refresh()

    def _optional_money(self, widget: QLineEdit) -> Decimal | None:
        raw = widget.text().strip()
        if not raw:
            return None
        return parse_money(raw)

    def _created_range(self) -> tuple[datetime | None, datetime | None]:
        from datetime import date, timedelta
        preset = self.created_preset.currentData()
        if preset == "all":
            return None, None
        today = date.today()
        if preset == "year":
            start = datetime.combine(date(today.year, 1, 1), time.min)
        else:
            days = int(preset)
            start = datetime.combine(today - timedelta(days=days - 1), time.min)
        end = datetime.combine(today, time.max)
        return start, end

    def _current_filter(self) -> ProductFilter:
        status_index = self.status.currentIndex()
        active = None if status_index == 0 else status_index == 1
        return ProductFilter(
            search=self.search.text(),
            product_id=self.id_exact.value() or None,
            id_min=self.id_min.value() or None,
            id_max=self.id_max.value() or None,
            category=self.category.currentData(),
            brand=self.brand.currentData(),
            active=active,
            stock_status=self.stock_status.currentData(),
            price_min=self._optional_money(self.price_min),
            price_max=self._optional_money(self.price_max),
            created_from=self._created_range()[0],
            created_to=self._created_range()[1],
            sort_by=self.sort_by.currentData(),
            sort_direction=self.sort_direction.currentData(),
        )

    def refresh(self):
        if not hasattr(self, "table"):
            return
        try:
            filters = self._current_filter()
            products, total = self.service.list_products_page(filters=filters, page=self._page, page_size=self._page_size)
        except Exception as exc:
            show_error(self, str(exc))
            return

        import math
        self._total_results = int(total)
        page_count = max(1, math.ceil(self._total_results / self._page_size))
        if self._page > page_count:
            self._page = page_count
            products, total = self.service.list_products_page(filters=filters, page=self._page, page_size=self._page_size)
            self._total_results = int(total)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self._visible_products = list(products)
        for p in products:
            status = "ACTIVO" if p.active else "INACTIVO"
            stock = str(p.stock_current)
            add_row(self.table, [
                "", str(p.id), p.sku, p.name, p.category, p.brand,
                fmt_money(p.sale_price), stock, str(p.stock_min), status,
                "Activar/Desactivar",
            ])
            row = self.table.rowCount() - 1
            self.table.setRowHeight(row, 72)
            photo_item = self.table.item(row, 0)
            pixmap = product_pixmap(p, QSize(60, 60))
            if not pixmap.isNull():
                photo_item.setIcon(QIcon(pixmap))
                photo_item.setToolTip("Clic para ampliar la imagen")
                photo_item.setText("")
            else:
                photo_item.setText("Sin foto")
                photo_item.setToolTip("Clic para consultar la imagen del producto")
            photo_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        page_count = max(1, math.ceil(self._total_results / self._page_size))
        self.page_status.setText(f"Página {self._page} de {page_count} · {self._total_results:,} resultados".replace(",", "."))
        self.prev_page.setEnabled(self._page > 1)
        self.next_page.setEnabled(self._page < page_count)
        self.filter_summary.setText(self._summary_text(filters, self._total_results))

    def _reset_and_refresh(self):
        self._page = 1
        self.refresh()

    def _previous_page(self):
        if self._page > 1:
            self._page -= 1
            self.refresh()

    def _next_page(self):
        import math
        page_count = max(1, math.ceil(self._total_results / self._page_size))
        if self._page < page_count:
            self._page += 1
            self.refresh()

    def _summary_text(self, filters: ProductFilter, count: int) -> str:
        if not filters.has_filters:
            return f"{count} productos"
        labels: list[str] = []
        if filters.search:
            labels.append("búsqueda")
        if filters.product_id is not None:
            labels.append("ID")
        elif filters.id_min is not None or filters.id_max is not None:
            labels.append("rango de ID")
        if filters.category:
            labels.append("categoría")
        if filters.brand:
            labels.append("marca")
        if filters.active is not None:
            labels.append("estado")
        if filters.stock_status != "all":
            labels.append("stock")
        if filters.price_min is not None or filters.price_max is not None:
            labels.append("precio")
        if filters.created_from is not None:
            labels.append("fecha")
        return f"{count} resultados · filtros: {', '.join(labels)}"

    def reset_filters(self):
        self._building_filters = True
        try:
            with QSignalBlocker(self.search), QSignalBlocker(self.category), QSignalBlocker(self.brand), QSignalBlocker(self.status), QSignalBlocker(self.stock_status), QSignalBlocker(self.id_exact), QSignalBlocker(self.id_min), QSignalBlocker(self.id_max), QSignalBlocker(self.price_min), QSignalBlocker(self.price_max), QSignalBlocker(self.created_preset), QSignalBlocker(self.sort_by), QSignalBlocker(self.sort_direction):
                self.search.clear()
                self.category.setCurrentIndex(0)
                self.brand.setCurrentIndex(0)
                self.status.setCurrentIndex(0)
                self.stock_status.setCurrentIndex(0)
                self.id_exact.setValue(0)
                self.id_min.setValue(0)
                self.id_max.setValue(0)
                self.price_min.clear()
                self.price_max.clear()
                self.created_preset.setCurrentIndex(0)
                self.sort_by.setCurrentIndex(0)
                self.sort_direction.setCurrentIndex(0)
        finally:
            self._building_filters = False
        self._page = 1
        self.refresh()

    def _handle_click(self, row: int, column: int):
        if column == 0:
            if 0 <= row < len(self._visible_products):
                product = self._visible_products[row]
                full_product = self.service.get_product(product.id)
                if full_product:
                    ProductImageDialog(full_product.name, full_product.image_data, full_product.image_path, self).exec()
            return
        if column != 10:
            return
        product_id = int(self.table.item(row, 1).text())
        try:
            self.service.toggle_product(product_id)
            self._load_filter_options()
            self.refresh()
        except Exception as exc:
            show_error(self, str(exc))

    def new_product(self):
        dlg = ProductDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            self.service.create_product(**dlg.values())
            self._load_filter_options()
            self.refresh()
            show_info(self, "Producto creado correctamente.")
        except Exception as exc:
            show_error(self, str(exc))

    def edit_product(self, row: int, column: int):
        if column == 0:
            return
        product_id = int(self.table.item(row, 1).text())
        product = self.service.get_product(product_id)
        if not product:
            return
        dlg = ProductDialog(self, product)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            self.service.update_product(product_id, **dlg.values())
            self._load_filter_options()
            self.refresh()
            show_info(self, "Producto actualizado correctamente.")
        except Exception as exc:
            show_error(self, str(exc))
