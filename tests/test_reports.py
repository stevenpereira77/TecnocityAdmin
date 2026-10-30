from datetime import datetime
from decimal import Decimal
import csv

from openpyxl import load_workbook

from app.database import create_database_engine, create_session_factory, initialize_database
from app.reports import ReportService
from app.reports.exporters import export_csv, export_excel, export_pdf
from app.reports.print_service import report_html
from app.services import StoreService


def services():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = create_session_factory(engine)
    store = StoreService(factory)
    return store, store.report_service


def seed(store: StoreService):
    mouse = store.create_product(sku="REP-1", name="Mouse Pro", category="Accesorios", brand="Tec", sale_price="100.00", stock_min=1)
    keyboard = store.create_product(sku="REP-2", name="Teclado Pro", category="Accesorios", brand="Tec", sale_price="150.00", stock_min=1)
    store.register_purchase(
        supplier="Proveedor Uno",
        items=[
            {"product_id": mouse.id, "quantity": 4, "unit_cost": "40.00"},
            {"product_id": keyboard.id, "quantity": 2, "unit_cost": "90.00"},
        ],
        shipping_cost="10.00",
        purchase_date=datetime(2026, 9, 10, 9, 0),
    )
    sale = store.register_sale(
        items=[{"product_id": mouse.id, "quantity": 2, "unit_sale_price": "100.00"}],
        payment_method="Nequi",
        customer_name="Ana Pérez",
        sale_date=datetime(2026, 9, 12, 14, 0),
    )
    store.register_expense(
        category="Publicidad",
        description="Campaña local",
        amount="25.00",
        expense_date=datetime(2026, 9, 13, 10, 0),
    )
    sale_item_id = store.get_sale(sale.id).items[0].id
    store.return_sale(
        sale_id=sale.id,
        items=[{"sale_item_id": sale_item_id, "quantity": 1}],
        reason="Cambio del cliente",
        return_date=datetime(2026, 9, 14, 11, 0),
    )
    cancelled = store.register_sale(
        items=[{"product_id": keyboard.id, "quantity": 1, "unit_sale_price": "150.00"}],
        payment_method="Efectivo",
        customer_name="Carlos",
        sale_date=datetime(2026, 9, 15, 15, 0),
    )
    store.cancel_sale(sale_id=cancelled.id, reason="Venta anulada", cancel_date=datetime(2026, 9, 16, 16, 0))


def test_report_catalog_is_explicit_and_complete():
    _, reports = services()
    keys = [definition.key for definition in reports.definitions()]
    assert keys == ["sales", "purchases", "inventory", "profitability", "expenses", "returns", "cancellations", "audit"]
    assert all(definition.columns for definition in reports.definitions())


def test_reports_build_expected_rows_and_financial_values():
    store, reports = services()
    seed(store)
    kwargs = {"period": "custom", "start": datetime(2026, 9, 1), "end": datetime(2026, 9, 30, 23, 59, 59)}

    sales = reports.build("sales", **kwargs)
    assert len(sales.rows) == 2
    cancelled = next(row for row in sales.rows if row["status"] == "CANCELADA")
    returned = next(row for row in sales.rows if row["status"] == "DEVOLUCION_PARCIAL")
    assert cancelled["net_total"] == Decimal("0.00")
    assert returned["net_total"] == Decimal("100.00")
    assert returned["refunded"] == Decimal("100.00")
    assert sales.summary[1][0] == "Ventas netas"

    purchases = reports.build("purchases", **kwargs)
    assert len(purchases.rows) == 1
    assert purchases.rows[0]["total"] == Decimal("350.00")

    inventory = reports.build("inventory")
    assert len(inventory.rows) == 2
    assert inventory.summary[2][0] == "Valor inventario"

    profitability = reports.build("profitability", **kwargs)
    assert len(profitability.rows) == 30
    assert sum(row["sales"] for row in profitability.rows) == Decimal("100.00")
    assert sum(row["general_expenses"] for row in profitability.rows) == Decimal("25.00")

    expenses = reports.build("expenses", **kwargs)
    assert len(expenses.rows) == 1
    assert expenses.rows[0]["category"] == "Publicidad"

    returns = reports.build("returns", **kwargs)
    assert len(returns.rows) == 1
    partial_return = next(row for row in returns.rows if row["customer"] == "Ana Pérez")
    assert partial_return["total_refunded"] == Decimal("100.00")
    assert partial_return["cogs_returned"] > 0

    cancellations = reports.build("cancellations", **kwargs)
    assert len(cancellations.rows) == 1
    assert cancellations.rows[0]["reason"] == "Venta anulada"

    # AuditLog.occurred_at records when the operation was performed, not the
    # historical sale_date supplied by the fixture. Keep this assertion tied
    # to the current execution day so it remains deterministic across dates.
    audit_now = datetime.now()
    audit = reports.build(
        "audit",
        period="custom",
        start=audit_now.replace(hour=0, minute=0, second=0, microsecond=0),
        end=audit_now.replace(hour=23, minute=59, second=59, microsecond=999999),
    )
    assert len(audit.rows) >= 6


def test_report_exporters_create_readable_files(tmp_path):
    store, reports = services()
    seed(store)
    result = reports.build(
        "sales",
        period="custom",
        start=datetime(2026, 9, 1),
        end=datetime(2026, 9, 30, 23, 59, 59),
    )

    csv_path = export_csv(result, tmp_path / "ventas.csv")
    excel_path = export_excel(result, tmp_path / "ventas.xlsx")
    pdf_path = export_pdf(result, tmp_path / "ventas.pdf")

    assert csv_path.exists() and csv_path.stat().st_size > 50
    assert excel_path.exists() and excel_path.stat().st_size > 500
    assert pdf_path.exists() and pdf_path.read_bytes().startswith(b"%PDF")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        lines = list(csv.reader(handle))
    assert lines[0] == ["Reporte", "Ventas"]
    assert ["Fecha", "Venta", "Estado"] == lines[5][:3]

    workbook = load_workbook(excel_path, read_only=False, data_only=False)
    sheet = workbook["Reporte"]
    assert sheet.cell(1, 1).value == "Ventas"
    assert sheet.cell(10, 1).value == "Fecha"
    assert sheet.freeze_panes == "A11"
    assert sheet.max_row >= 12
    workbook.close()


def test_all_report_types_have_exportable_output(tmp_path):
    store, reports = services()
    seed(store)
    kwargs = {"period": "custom", "start": datetime(2026, 9, 1), "end": datetime(2026, 9, 30, 23, 59, 59)}
    for definition in reports.definitions():
        result = reports.build(definition.key, **(kwargs if definition.date_filtered else {}))
        csv_path = export_csv(result, tmp_path / f"{definition.key}.csv")
        excel_path = export_excel(result, tmp_path / f"{definition.key}.xlsx")
        pdf_path = export_pdf(result, tmp_path / f"{definition.key}.pdf")
        assert csv_path.exists()
        assert excel_path.exists()
        assert pdf_path.read_bytes().startswith(b"%PDF")


def test_excel_export_supports_empty_reports(tmp_path):
    _, reports = services()
    result = reports.build(
        "sales",
        period="custom",
        start=datetime(2026, 9, 1),
        end=datetime(2026, 9, 30, 23, 59, 59),
    )
    path = export_excel(result, tmp_path / "empty.xlsx")
    workbook = load_workbook(path, read_only=False)
    assert workbook["Reporte"].cell(10, 1).value == "Fecha"
    workbook.close()


def test_print_html_is_renderable_without_qt():
    store, reports = services()
    seed(store)
    result = reports.build("sales", period="custom", start=datetime(2026, 9, 1), end=datetime(2026, 9, 30, 23, 59, 59))
    html = report_html(result)
    assert "<table>" in html
    assert "Venta neta" in html
    assert "DEVOLUCION_PARCIAL" in html
    assert "Ana Pérez" in html
