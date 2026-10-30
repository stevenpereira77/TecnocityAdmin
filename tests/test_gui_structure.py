import ast
from pathlib import Path
import importlib.util
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_main_window_module_can_be_imported():
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no está instalado en el entorno de validación.")
    module = __import__("app.views.main_window", fromlist=["MainWindow"])
    assert hasattr(module, "MainWindow")


def test_main_window_adds_sidebar_widget_not_layout():
    source = (ROOT / "app" / "views" / "main_window.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "addWidget"
    ]
    assert any(
        len(node.args) == 1 and isinstance(node.args[0], ast.Name) and node.args[0].id == "sidebar"
        for node in calls
    )


def test_transaction_gui_does_not_convert_money_to_float_or_use_double_spin_box():
    source = (ROOT / "app" / "widgets" / "transaction_pages.py").read_text(encoding="utf-8")
    assert "QDoubleSpinBox" not in source
    tree = ast.parse(source)
    float_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float"
    ]
    assert not float_calls


def test_sales_gui_contains_explicit_shipping_payer_controls():
    source = (ROOT / "app" / "widgets" / "transaction_pages.py").read_text(encoding="utf-8")
    assert "shipping_payer" in source
    assert "shipping_cost" in source
    assert "shipping_charge" in source
    assert "SHIPPING_CUSTOMER_DIRECT" in source
    assert "SHIPPING_PAYER_LABELS" in source
    assert "Devolver" in source
    assert "Cancelar venta" in source


def test_qheader_resize_mode_uses_enum_not_numeric():
    source = (Path(__file__).parents[1] / "app" / "widgets" / "transaction_pages.py").read_text(encoding="utf-8")
    assert "setSectionResizeMode(0, 1)" not in source
    assert "setSectionResizeMode(4, 1)" not in source
    helpers = (Path(__file__).parents[1] / "app" / "widgets" / "ui_helpers.py").read_text(encoding="utf-8")
    assert "QHeaderView.ResizeMode.ResizeToContents" in helpers
    assert "fit_table(" in source


def test_all_qheader_resize_modes_are_enums():
    targets = (
        ROOT / "app/widgets/ui_helpers.py",
        ROOT / "app/widgets/products_page.py",
        ROOT / "app/widgets/transaction_pages.py",
    )
    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "setSectionResizeMode"
            ):
                continue
            assert len(node.args) in {1, 2}
            mode_arg = node.args[-1]
            assert isinstance(mode_arg, ast.Attribute)
            if isinstance(mode_arg.value, ast.Name):
                assert mode_arg.value.id == "QHeaderView"
            else:
                assert isinstance(mode_arg.value, ast.Attribute)
                assert mode_arg.value.attr == "ResizeMode"
                assert isinstance(mode_arg.value.value, ast.Name)
                assert mode_arg.value.value.id == "QHeaderView"


def test_dashboard_gui_has_executive_filters_charts_tables_and_scroll():
    source = (ROOT / "app" / "widgets" / "dashboard_page.py").read_text(encoding="utf-8")
    assert "QScrollArea" in source
    assert "DashboardLineChart" in source
    assert "DashboardDonutChart" in source
    assert "DashboardHorizontalBarChart" in source
    assert "PySide6.QtCharts" not in source
    assert "dashboard_report" in source
    assert '"Personalizado"' in source
    assert '"Productos más rentables"' in source
    assert '"Alertas y operación"' in source
    assert '"Ventas netas"' in source
    assert '"Ticket promedio"' in source
    assert '"Margen neto"' in source


def test_dashboard_does_not_silently_swallow_refresh_exceptions():
    source = (ROOT / "app" / "widgets" / "dashboard_page.py").read_text(encoding="utf-8")
    assert "except Exception:" not in source


def test_dashboard_financial_math_stays_in_service_layer():
    source = (ROOT / "app" / "widgets" / "dashboard_page.py").read_text(encoding="utf-8")
    assert "* Decimal(" not in source
    assert "dashboard_report" in source


def test_dashboard_lower_panels_use_a_symmetric_horizontal_layout():
    source = (ROOT / "app" / "widgets" / "dashboard_page.py").read_text(encoding="utf-8")
    assert "lower_layout = QHBoxLayout()" in source
    assert "lower_layout.addWidget(performance, 1)" in source
    assert "lower_layout.addWidget(alerts, 1)" in source
    assert "lower_grid.addWidget(performance, 0, 0, 1, 2)" not in source
    assert "lower_grid.addWidget(alerts, 1, 2)" not in source



def test_dashboard_widget_can_be_constructed_when_qt_is_available(monkeypatch):
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no está instalado en el entorno de validación.")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QScrollArea
    from app.widgets.dashboard_page import DashboardPage
    from decimal import Decimal
    from datetime import datetime

    class FakeService:
        def dashboard_report(self, **kwargs):
            return {
                "start": datetime(2026, 9, 1),
                "end": datetime(2026, 9, 29),
                "current": {
                    "sales": Decimal("1000.00"), "profit": Decimal("300.00"), "expenses": Decimal("100.00"),
                    "margin": Decimal("30.00"), "average_ticket": Decimal("100.00"), "operations": 10,
                    "gross_profit": Decimal("400.00"),
                },
                "changes": {"sales": Decimal("10.00"), "profit": Decimal("5.00"), "expenses": Decimal("-2.00"), "average_ticket": Decimal("1.00"), "margin": Decimal("2.00")},
                "trend": [{"label": "01/09", "sales": Decimal("100.00"), "profit": Decimal("20.00"), "expenses": Decimal("5.00"), "operations": 1}],
                "payment_methods": [{"name": "Efectivo", "value": Decimal("1000.00")}],
                "expense_categories": [{"name": "Publicidad", "value": Decimal("100.00")}],
                "top_products": [{"name": "Producto", "sku": "P-1", "units": 10, "revenue": Decimal("500.00"), "cogs": Decimal("300.00"), "profit": Decimal("200.00"), "margin": Decimal("40.00")}],
                "top_profitable_products": [{"name": "Producto", "sku": "P-1", "units": 10, "revenue": Decimal("500.00"), "cogs": Decimal("300.00"), "profit": Decimal("200.00"), "margin": Decimal("40.00")}],
                "low_products": [], "out_products": [],
                "inventory": {"value": Decimal("2500.00"), "invested": Decimal("5000.00"), "products_count": 12, "low_stock": 0, "out_of_stock": 0},
                "shipping": {"store_cost": Decimal("20.00"), "customer_charged": Decimal("30.00")},
            }

    app = QApplication.instance() or QApplication([])
    page = DashboardPage(FakeService())
    assert len(page.cards) == 8
    assert len(page.findChildren(QScrollArea)) == 1
    assert page.products_table.columnCount() == 5
    assert page.alert_table.columnCount() == 4
    assert page.trend_chart.row_count() == 1
    assert page.payment_chart.row_count() == 1
    assert page.products_chart.row_count() == 1
    assert page.expenses_chart.row_count() == 1
    page.deleteLater()
    app.processEvents()


def test_dashboard_custom_dates_are_guarded_and_mutually_constrained():
    source = (ROOT / "app" / "widgets" / "dashboard_page.py").read_text(encoding="utf-8")
    assert "QSignalBlocker" in source
    assert "setMaximumDate(end)" in source
    assert "setMinimumDate(start)" in source
    assert "if start > end:" in source
    assert "Rango inválido:" in source


def test_dashboard_refresh_handles_invalid_custom_range_without_uncaught_exception():
    source = (ROOT / "app" / "widgets" / "dashboard_page.py").read_text(encoding="utf-8")
    refresh_pos = source.index("    def refresh(self) -> None:")
    refresh = source[refresh_pos:]
    assert "try:" in refresh
    assert "except ValueError as exc:" in refresh
    assert "self.service.dashboard_report(**self._report_kwargs())" in refresh


def test_dashboard_charts_do_not_import_the_separately_licensed_qt_charts_module():
    source = (ROOT / "app" / "widgets" / "dashboard_charts.py").read_text(encoding="utf-8")
    assert "PySide6.QtCharts" not in source
    assert "QPainter" in source
    assert "DashboardLineChart" in source
    assert "DashboardDonutChart" in source
    assert "DashboardHorizontalBarChart" in source
