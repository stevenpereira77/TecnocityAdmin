from decimal import Decimal
from datetime import datetime

from app.database import create_database_engine, create_session_factory, initialize_database
from app.models import InventoryLayer
from app.services import (
    SHIPPING_CUSTOMER_DIRECT,
    SHIPPING_CUSTOMER_ORDER,
    SHIPPING_STORE,
    StoreService,
)


def service():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    return StoreService(create_session_factory(engine))


def test_purchase_sale_fifo_freezes_cogs_and_stock():
    svc = service()
    p = svc.create_product(sku="FIFO-1", name="Cable", sale_price="100.00", stock_min=1)
    svc.register_purchase(supplier="Proveedor A", items=[{"product_id": p.id, "quantity": 10, "unit_cost": "20.00"}])
    svc.register_purchase(supplier="Proveedor B", items=[{"product_id": p.id, "quantity": 10, "unit_cost": "25.00"}])
    sale = svc.register_sale(items=[{"product_id": p.id, "quantity": 12, "unit_sale_price": "100.00"}])
    assert sale.cogs == Decimal("250.00")
    assert sale.total == Decimal("1200.00")
    assert sale.gross_profit == Decimal("950.00")
    assert sale.net_profit == Decimal("950.00")
    assert svc.get_product(p.id).stock_current == 8


def test_purchase_cost_allocates_extra_costs_to_fifo_layer():
    svc = service()
    p = svc.create_product(sku="SHIP-1", name="Adapter", sale_price="50.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 2, "unit_cost": "10.00"}], shipping_cost="4.00")
    layers = svc.inventory_rows()
    assert layers[0]["value"] == Decimal("24.00")


def test_general_expense_reduces_dashboard_accumulated_profit():
    svc = service()
    p = svc.create_product(sku="EXP-1", name="Mouse", sale_price="100.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 1, "unit_cost": "40.00"}])
    svc.register_sale(items=[{"product_id": p.id, "quantity": 1, "unit_sale_price": "100.00"}])
    svc.register_expense(category="Publicidad", description="Ads", amount="10.00")
    data = svc.dashboard()
    assert data["profit_all"] == Decimal("50.00")


def test_negative_stock_adjustment_is_rejected():
    svc = service()
    p = svc.create_product(sku="ADJ-1", name="Keyboard", sale_price="100.00")
    try:
        svc.adjust_stock(product_id=p.id, quantity=-1, reason="Corrección")
        assert False, "expected validation error"
    except Exception as exc:
        assert "por debajo" in str(exc)


def test_direct_sale_expense_updates_that_sale_profit():
    svc = service()
    p = svc.create_product(sku="DIR-1", name="Hub", sale_price="100.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 1, "unit_cost": "30.00"}])
    sale = svc.register_sale(items=[{"product_id": p.id, "quantity": 1, "unit_sale_price": "100.00"}])
    svc.register_expense(category="Comisiones", description="Marketplace", amount="7.00", direct_sale=True, sale_id=sale.id)
    refreshed = svc.sales()[0]
    assert refreshed.net_profit == Decimal("63.00")


def test_product_update_keeps_stock_and_changes_catalog_fields():
    svc = service()
    p = svc.create_product(sku="UP-1", name="Original", sale_price="10.00", stock_min=2)
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 5, "unit_cost": "4.00"}])
    svc.update_product(p.id, name="Actualizado", sale_price="12.00", stock_min=3)
    updated = svc.get_product(p.id)
    assert updated.name == "Actualizado"
    assert updated.sale_price == Decimal("12.00")
    assert updated.stock_current == 5


def test_money_accepts_colombian_string_and_positive_adjustment_creates_layer():
    svc = service()
    p = svc.create_product(sku="ADJ-P", name="Producto ajuste", sale_price="100,00")
    svc.adjust_stock(product_id=p.id, quantity=5, reason="Conteo físico")
    product = svc.get_product(p.id)
    assert product.stock_current == 5
    assert svc.inventory_rows()[0]["value"] == Decimal("0.00")
    assert svc.movements()[0].movement_type == "AJUSTE_POSITIVO"


def test_shipping_store_pays_reduces_profit_and_no_shipping_revenue():
    svc = service()
    p = svc.create_product(sku="SHP-1", name="Producto", sale_price="100.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 1, "unit_cost": "40.00"}])
    sale = svc.register_sale(
        items=[{"product_id": p.id, "quantity": 1, "unit_sale_price": "100.00"}],
        shipping_cost="10.00",
        shipping_payer=SHIPPING_STORE,
    )
    assert sale.total == Decimal("100.00")
    assert sale.net_profit == Decimal("50.00")


def test_shipping_customer_pays_in_order_adds_charge_and_pass_through():
    svc = service()
    p = svc.create_product(sku="SHP-2", name="Producto", sale_price="100.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 1, "unit_cost": "40.00"}])
    sale = svc.register_sale(
        items=[{"product_id": p.id, "quantity": 1, "unit_sale_price": "100.00"}],
        shipping_cost="10.00",
        shipping_charge="10.00",
        shipping_payer=SHIPPING_CUSTOMER_ORDER,
    )
    assert sale.total == Decimal("110.00")
    assert sale.net_profit == Decimal("60.00")
    data = svc.dashboard()
    assert data["shipping_charged_all"] == Decimal("10.00")
    assert data["shipping_all"] == Decimal("10.00")


def test_shipping_customer_pays_direct_does_not_affect_store_profit():
    svc = service()
    p = svc.create_product(sku="SHP-3", name="Producto", sale_price="100.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 1, "unit_cost": "40.00"}])
    sale = svc.register_sale(
        items=[{"product_id": p.id, "quantity": 1, "unit_sale_price": "100.00"}],
        shipping_cost="10.00",
        shipping_payer=SHIPPING_CUSTOMER_DIRECT,
    )
    assert sale.total == Decimal("100.00")
    assert sale.net_profit == Decimal("60.00")
    assert svc.dashboard()["shipping_all"] == Decimal("0.00")


def test_partial_return_restores_fifo_cost_and_reduces_effective_sale():
    svc = service()
    p = svc.create_product(sku="RET-1", name="Producto retorno", sale_price="100.00")
    svc.register_purchase(supplier="A", items=[{"product_id": p.id, "quantity": 2, "unit_cost": "40.00"}])
    svc.register_purchase(supplier="B", items=[{"product_id": p.id, "quantity": 2, "unit_cost": "50.00"}])
    sale = svc.register_sale(items=[{"product_id": p.id, "quantity": 3, "unit_sale_price": "100.00"}])
    assert sale.cogs == Decimal("130.00")
    assert svc.get_product(p.id).stock_current == 1
    item = svc.get_sale(sale.id).items[0]
    ret = svc.return_sale(sale_id=sale.id, items=[{"sale_item_id": item.id, "quantity": 1}], reason="Cliente devuelve una unidad")
    assert ret.cogs_returned == Decimal("40.00")
    assert ret.total_refunded == Decimal("100.00")
    assert svc.get_product(p.id).stock_current == 2
    summary = svc.sale_summary(sale.id)
    assert summary["status"] == "DEVOLUCION_PARCIAL"
    assert summary["net_total"] == Decimal("200.00")
    assert summary["current_profit"] == Decimal("110.00")
    assert svc.movements()[0].movement_type == "DEVOLUCION"


def test_full_cancel_restores_all_remaining_inventory_and_keeps_audit_trail():
    svc = service()
    p = svc.create_product(sku="CAN-1", name="Producto cancelar", sale_price="100.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 2, "unit_cost": "30.00"}])
    sale = svc.register_sale(items=[{"product_id": p.id, "quantity": 2, "unit_sale_price": "100.00"}])
    assert svc.get_product(p.id).stock_current == 0
    svc.cancel_sale(sale_id=sale.id, reason="Cliente canceló el pedido")
    assert svc.get_product(p.id).stock_current == 2
    summary = svc.sale_summary(sale.id)
    assert summary["status"] == "CANCELADA"
    assert summary["net_total"] == Decimal("0.00")
    assert summary["current_profit"] == Decimal("0.00")
    assert any(a.action == "CANCELAR" for a in svc.audit_logs())


def test_delivery_status_is_explicit_and_audited():
    svc = service()
    p = svc.create_product(sku="DEL-1", name="Entrega", sale_price="50.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 1, "unit_cost": "20.00"}])
    sale = svc.register_sale(items=[{"product_id": p.id, "quantity": 1, "unit_sale_price": "50.00"}])
    svc.update_delivery_status(sale.id, "ENVIADA")
    summary = svc.sale_summary(sale.id)
    assert summary["delivery_status"] == "ENVIADA"
    assert any(a.action == "CAMBIAR_ESTADO" and "ENVIADA" in a.details for a in svc.audit_logs())


def test_duplicate_product_lines_are_aggregated_by_stock_validation():
    svc = service()
    p = svc.create_product(sku="DUP-1", name="Duplicado", sale_price="20.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 2, "unit_cost": "5.00"}])
    try:
        svc.register_sale(items=[
            {"product_id": p.id, "quantity": 2, "unit_sale_price": "20.00"},
            {"product_id": p.id, "quantity": 1, "unit_sale_price": "20.00"},
        ])
        assert False, "expected stock validation"
    except Exception as exc:
        assert "Disponible" in str(exc)


def test_sale_is_atomic_when_a_later_line_fails_stock_validation():
    svc = service()
    p1 = svc.create_product(sku="AT-1", name="A", sale_price="50.00")
    p2 = svc.create_product(sku="AT-2", name="B", sale_price="60.00")
    svc.register_purchase(supplier="Proveedor", items=[
        {"product_id": p1.id, "quantity": 1, "unit_cost": "20.00"},
        {"product_id": p2.id, "quantity": 0 + 1, "unit_cost": "25.00"},
    ])
    try:
        svc.register_sale(items=[
            {"product_id": p1.id, "quantity": 1, "unit_sale_price": "50.00"},
            {"product_id": p2.id, "quantity": 2, "unit_sale_price": "60.00"},
        ])
        assert False, "expected atomic stock validation"
    except Exception as exc:
        assert "Disponible" in str(exc)
    assert svc.get_product(p1.id).stock_current == 1
    assert svc.get_product(p2.id).stock_current == 1
    assert svc.sales() == []


def test_full_return_with_shipping_refund_preserves_nonrecoverable_shipping_cost_as_loss():
    svc = service()
    p = svc.create_product(sku="RET-S", name="Producto envío", sale_price="100.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 1, "unit_cost": "40.00"}])
    sale = svc.register_sale(
        items=[{"product_id": p.id, "quantity": 1, "unit_sale_price": "100.00"}],
        shipping_cost="10.00",
        shipping_charge="10.00",
        shipping_payer=SHIPPING_CUSTOMER_ORDER,
    )
    item = svc.get_sale(sale.id).items[0]
    ret = svc.return_sale(sale_id=sale.id, items=[{"sale_item_id": item.id, "quantity": 1}], reason="Devolución completa", refund_shipping=True)
    assert ret.total_refunded == Decimal("110.00")
    summary = svc.sale_summary(sale.id)
    assert summary["status"] == "DEVUELTA_COMPLETA"
    assert summary["net_total"] == Decimal("0.00")
    assert summary["current_profit"] == Decimal("-10.00")
    assert svc.get_product(p.id).stock_current == 1


def test_cancel_after_partial_return_only_restores_remaining_units():
    svc = service()
    p = svc.create_product(sku="CAN-P", name="Cancelación parcial", sale_price="80.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 3, "unit_cost": "30.00"}])
    sale = svc.register_sale(items=[{"product_id": p.id, "quantity": 3, "unit_sale_price": "80.00"}])
    item = svc.get_sale(sale.id).items[0]
    svc.return_sale(sale_id=sale.id, items=[{"sale_item_id": item.id, "quantity": 1}], reason="Primera devolución")
    assert svc.get_product(p.id).stock_current == 1
    svc.cancel_sale(sale_id=sale.id, reason="Cancelar lo restante")
    assert svc.get_product(p.id).stock_current == 3
    assert svc.sale_summary(sale.id)["status"] == "CANCELADA"


def test_invalid_shipping_charge_for_direct_customer_payment_is_rejected():
    svc = service()
    p = svc.create_product(sku="SHP-X", name="Producto", sale_price="100.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 1, "unit_cost": "30.00"}])
    try:
        svc.register_sale(
            items=[{"product_id": p.id, "quantity": 1, "unit_sale_price": "100.00"}],
            shipping_cost="8.00",
            shipping_charge="8.00",
            shipping_payer=SHIPPING_CUSTOMER_DIRECT,
        )
        assert False, "expected validation error"
    except Exception as exc:
        assert "solo puede cobrarse domicilio" in str(exc).lower()


def test_financial_money_rejects_float_in_internal_business_calculator():
    from app.calculations.financial import money
    try:
        money(10.5)  # type: ignore[arg-type]
        assert False, "float must not enter internal financial calculations"
    except TypeError as exc:
        assert "float" in str(exc)


def test_full_cancel_keeps_nonrecoverable_sale_costs_in_business_result():
    svc = service()
    p = svc.create_product(sku="CAN-C", name="Cancel con costos", sale_price="100.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 1, "unit_cost": "40.00"}])
    sale = svc.register_sale(
        items=[{"product_id": p.id, "quantity": 1, "unit_sale_price": "100.00"}],
        shipping_cost="10.00",
        commission="5.00",
        other_cost="3.00",
    )
    svc.cancel_sale(sale_id=sale.id, reason="Pedido cancelado", refund_shipping=True)
    assert svc.sale_summary(sale.id)["current_profit"] == Decimal("-18.00")
    assert svc.dashboard()["profit_all"] == Decimal("-18.00")


def test_customer_shipping_refund_is_explicit_and_capped_at_unrefunded_charge():
    svc = service()
    p = svc.create_product(sku="RFD-1", name="Reembolso envío", sale_price="100.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 2, "unit_cost": "40.00"}])
    sale = svc.register_sale(
        items=[{"product_id": p.id, "quantity": 2, "unit_sale_price": "100.00"}],
        shipping_cost="12.00",
        shipping_charge="12.00",
        shipping_payer=SHIPPING_CUSTOMER_ORDER,
    )
    item = svc.get_sale(sale.id).items[0]
    first = svc.return_sale(sale_id=sale.id, items=[{"sale_item_id": item.id, "quantity": 1}], reason="Primera devolución", refund_shipping=True)
    assert first.shipping_refunded == Decimal("12.00")
    second = svc.return_sale(sale_id=sale.id, items=[{"sale_item_id": item.id, "quantity": 1}], reason="Segunda devolución", refund_shipping=True)
    assert second.shipping_refunded == Decimal("0.00")
    assert svc.sale_summary(sale.id)["net_total"] == Decimal("0.00")


def test_sale_preview_matches_registration_formula_without_mutating_stock():
    svc = service()
    p = svc.create_product(sku="PREV-1", name="Vista previa", sale_price="100.00")
    svc.register_purchase(supplier="Proveedor", items=[{"product_id": p.id, "quantity": 2, "unit_cost": "40.00"}])
    preview = svc.preview_sale(
        items=[{"product_id": p.id, "quantity": 1, "unit_sale_price": "100.00"}],
        shipping_cost="8.00",
        shipping_charge="8.00",
        shipping_payer=SHIPPING_CUSTOMER_ORDER,
        commission="5.00",
    )
    assert preview["total"] == Decimal("108.00")
    assert preview["cogs"] == Decimal("40.00")
    assert preview["gross_profit"] == Decimal("68.00")
    assert preview["net_profit"] == Decimal("55.00")
    assert svc.get_product(p.id).stock_current == 2
