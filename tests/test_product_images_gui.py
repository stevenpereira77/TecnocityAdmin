from __future__ import annotations

import importlib.util

import pytest

if importlib.util.find_spec("PySide6") is None:
    pytest.skip("PySide6 no está instalado en el entorno de validación.", allow_module_level=True)


def test_product_image_ui_and_thumbnail_encoding_without_layout_overflow(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    from app.database import create_database_engine, create_session_factory, initialize_database
    from app.services import StoreService
    from app.utils.product_images import encode_product_image, encode_product_thumbnail
    from app.widgets.inventory_page import InventoryPage
    from app.widgets.products_page import ProductDialog, ProductsPage
    from app.widgets.transaction_pages import PurchasesPage

    app = QApplication.instance() or QApplication([])
    source = tmp_path / "product_photo.png"
    image = QImage(640, 400, QImage.Format.Format_RGB32)
    image.fill(QColor("#e7e7e7"))
    assert image.save(str(source), "PNG")
    image_data = encode_product_image(source)
    thumbnail_data = encode_product_thumbnail(image_data)
    assert image_data.startswith(b"\xff\xd8\xff")
    assert thumbnail_data.startswith(b"\xff\xd8\xff")
    assert len(image_data) <= 2 * 1024 * 1024
    assert len(thumbnail_data) <= 256 * 1024

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    service = StoreService(create_session_factory(engine))
    product = service.create_product(
        sku="VIS-001", name="Producto visual", sale_price="100.00",
        image_data=image_data, image_thumbnail_data=thumbnail_data,
    )

    editor = ProductDialog(product=service.get_product(product.id))
    assert editor.image_preview.pixmap() is not None
    assert not editor.image_preview.pixmap().isNull()
    assert editor.view_image_button.isEnabled()
    unchanged_values = editor.values()
    assert "image_data" not in unchanged_values

    catalogue = ProductsPage(service)
    catalogue.resize(1280, 820)
    catalogue.show()
    app.processEvents()
    assert catalogue.table.columnCount() == 11
    assert catalogue.table.rowCount() == 1
    assert not catalogue.table.item(0, 0).icon().isNull()
    assert catalogue.table.rowHeight(0) >= 64

    purchases = PurchasesPage(service)
    purchases.resize(1280, 900)
    purchases.show()
    app.processEvents()
    assert purchases.new_product_button.text() == "+ Nuevo producto"
    assert not purchases.product_image_button.icon().isNull()

    inventory = InventoryPage(service)
    inventory.resize(1280, 820)
    inventory.show()
    app.processEvents()
    assert inventory.table.columnCount() == 7
    assert inventory.table.rowCount() == 1
    assert not inventory.table.item(0, 0).icon().isNull()

    assert catalogue.sizeHint().width() > 0
    assert purchases.sizeHint().width() > 0
    assert inventory.sizeHint().width() > 0

    for widget in (editor, catalogue, purchases, inventory):
        widget.close()
        widget.deleteLater()
    app.processEvents()
    engine.dispose()
