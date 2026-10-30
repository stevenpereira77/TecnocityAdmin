"""Regresión v1.2.2: SalesPage fallaba al abrir con
AttributeError: 'SalesPage' object has no attribute 'total_label'
porque refresh_cart() se disparaba antes de construir los labels de total."""
import ast
import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "widgets" / "transaction_pages.py"


def _method(class_name: str, method_name: str) -> ast.FunctionDef:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == class_name):
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef) and fn.name == method_name:
                return fn
    raise AssertionError(f"{class_name}.{method_name} no encontrado")


def _self_calls(fn: ast.FunctionDef) -> set[str]:
    return {
        n.func.attr
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "self"
    }


def test_build_sale_fields_does_not_refresh_before_labels_exist():
    assert not {"refresh_cart", "_sync_shipping_mode"} & _self_calls(_method("CartPage", "_build_sale_fields"))


def test_refresh_cart_is_guarded_until_ui_is_ready():
    source = ast.get_source_segment(SOURCE.read_text(encoding="utf-8"), _method("CartPage", "refresh_cart"))
    assert "_ui_ready" in source.split("self.table.setRowCount", 1)[0]


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="PySide6 no está instalado.")
def test_sales_and_purchases_pages_can_be_created_offscreen():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app.database import create_database_engine, create_session_factory, initialize_database
    from app.services import StoreService
    from app.widgets.transaction_pages import PurchasesPage, SalesPage

    app = QApplication.instance() or QApplication([])
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    service = StoreService(create_session_factory(engine))
    sales, purchases = SalesPage(service), PurchasesPage(service)
    assert sales.total_label.text().startswith("Total:")
    assert purchases.total_label.text().startswith("Total:")
    assert app is not None


def test_payment_box_uses_grid_and_shipping_fields_follow_mode():
    source = SOURCE.read_text(encoding="utf-8")
    assert "QScrollArea" in source                      # la página ya no aplasta los formularios
    assert "shipping_charge.textEdited.connect(self._mark_charge_manual)" in source
    sync = ast.get_source_segment(source, _method("CartPage", "_sync_shipping_mode"))
    assert "shipping_cost.setEnabled" in sync and "shipping_charge.setEnabled" in sync
