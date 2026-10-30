from datetime import datetime
from decimal import Decimal

from app.database import create_database_engine, create_session_factory, initialize_database
from app.services import StoreService


def service():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    return StoreService(create_session_factory(engine))


def test_dashboard_report_returns_trend_payment_products_alerts_and_comparison():
    svc = service()
    now = datetime(2026, 9, 29, 18, 0)
    first = svc.create_product(sku="DASH-1", name="Mouse Pro", sale_price="100.00", stock_min=1)
    second = svc.create_product(sku="DASH-2", name="Teclado Pro", sale_price="80.00", stock_min=2)
    svc.register_purchase(
        supplier="Proveedor",
        items=[
            {"product_id": first.id, "quantity": 4, "unit_cost": "40.00"},
            {"product_id": second.id, "quantity": 2, "unit_cost": "30.00"},
        ],
        purchase_date=datetime(2026, 9, 20, 10, 0),
    )
    svc.register_sale(
        items=[{"product_id": first.id, "quantity": 1, "unit_sale_price": "100.00"}],
        payment_method="Nequi",
        sale_date=datetime(2026, 9, 24, 12, 0),
    )
    svc.register_sale(
        items=[
            {"product_id": first.id, "quantity": 1, "unit_sale_price": "100.00"},
            {"product_id": second.id, "quantity": 1, "unit_sale_price": "80.00"},
        ],
        discount="10.00",
        payment_method="Efectivo",
        sale_date=datetime(2026, 9, 28, 14, 0),
    )
    svc.register_expense(
        category="Publicidad",
        description="Campaña septiembre",
        amount="20.00",
        expense_date=datetime(2026, 9, 28, 16, 0),
    )

    report = svc.dashboard_report(period="7d", now=now)

    assert report["start"] == datetime(2026, 9, 23)
    assert report["end"] == now
    assert report["current"]["sales"] == Decimal("270.00")
    assert report["current"]["expenses"] == Decimal("20.00")
    assert report["current"]["operations"] == 2
    assert report["current"]["margin"] == Decimal("51.85")
    assert len(report["trend"]) == 7
    assert {row["label"] for row in report["trend"] if row["sales"]} == {"24/09", "28/09"}
    assert [row["name"] for row in report["payment_methods"]] == ["Efectivo", "Nequi"]
    assert report["payment_methods"][0]["value"] == Decimal("170.00")
    assert report["payment_methods"][1]["value"] == Decimal("100.00")
    assert report["top_products"][0]["name"] == "Mouse Pro"
    assert report["top_products"][0]["units"] == 2
    assert report["top_profitable_products"][0]["name"] == "Mouse Pro"
    assert report["inventory"]["low_stock"] == 1
    assert report["inventory"]["out_of_stock"] == 0
    assert report["changes"]["sales"] is None


def test_dashboard_report_custom_range_and_empty_state_are_stable():
    svc = service()
    p = svc.create_product(sku="DASH-EMPTY", name="Producto", sale_price="50.00", stock_min=1)
    svc.register_purchase(
        supplier="Proveedor",
        items=[{"product_id": p.id, "quantity": 1, "unit_cost": "30.00"}],
        purchase_date=datetime(2026, 9, 1, 9, 0),
    )

    report = svc.dashboard_report(
        period="custom",
        start=datetime(2026, 9, 10),
        end=datetime(2026, 9, 12, 23, 59, 59, 999999),
        now=datetime(2026, 9, 29),
    )

    assert report["current"]["sales"] == Decimal("0.00")
    assert report["current"]["profit"] == Decimal("0.00")
    assert report["current"]["average_ticket"] == Decimal("0.00")
    assert report["payment_methods"] == []
    assert report["expense_categories"] == []
    assert len(report["trend"]) == 3
    assert report["inventory"]["value"] == Decimal("30.00")
