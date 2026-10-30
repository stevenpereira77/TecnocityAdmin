"""Regression tests for monetary reconciliation across partial returns/cancellations."""
from decimal import Decimal

import pytest

from app.core.exceptions import ValidationError
from app.database import create_database_engine, create_session_factory, initialize_database
from app.services import StoreService


def service() -> StoreService:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    return StoreService(create_session_factory(engine))


def add_stock(svc: StoreService, *, sku: str, unit_sale_price: str, quantity: int, unit_cost: str = "40.00"):
    product = svc.create_product(sku=sku, name=f"Producto {sku}", sale_price=unit_sale_price)
    svc.register_purchase(
        supplier="Proveedor de prueba",
        items=[{"product_id": product.id, "quantity": quantity, "unit_cost": unit_cost}],
    )
    return product


def return_one(svc: StoreService, sale_id: int, reason: str = "Prueba de devolución"):
    current_sale = svc.get_sale(sale_id)
    item = current_sale.items[0]
    return svc.return_sale(
        sale_id=sale_id,
        items=[{"sale_item_id": item.id, "quantity": 1}],
        reason=reason,
    )


def test_global_discount_is_refunded_exactly_across_two_partial_returns():
    svc = service()
    product = add_stock(svc, sku="RET-DISC-2", unit_sale_price="100.00", quantity=2)
    sale = svc.register_sale(
        items=[{"product_id": product.id, "quantity": 2, "unit_sale_price": "100.00"}],
        discount="20.00",
    )

    first = return_one(svc, sale.id, "Primera unidad")
    second = return_one(svc, sale.id, "Segunda unidad")

    assert first.products_refunded == Decimal("90.00")
    assert first.discount_refunded == Decimal("10.00")
    assert first.total_refunded == Decimal("90.00")
    assert second.products_refunded == Decimal("90.00")
    assert second.discount_refunded == Decimal("10.00")
    assert second.total_refunded == Decimal("90.00")

    assert first.total_refunded + second.total_refunded == sale.total == Decimal("180.00")
    assert first.discount_refunded + second.discount_refunded == sale.discount == Decimal("20.00")
    summary = svc.sale_summary(sale.id)
    assert summary["net_total"] == Decimal("0.00")
    assert summary["current_profit"] == Decimal("0.00")
    assert summary["status"] == "DEVUELTA_COMPLETA"
    assert svc.get_product(product.id).stock_current == 2


def test_line_discount_rounding_is_reconciled_on_three_separate_returns():
    svc = service()
    product = add_stock(svc, sku="RET-LINE-CENTS", unit_sale_price="10.00", quantity=3, unit_cost="1.00")
    sale = svc.register_sale(
        items=[{"product_id": product.id, "quantity": 3, "unit_sale_price": "10.00", "discount": "10.00"}],
    )
    assert sale.subtotal == Decimal("20.00")

    returns = [return_one(svc, sale.id, f"Unidad {index}") for index in range(1, 4)]
    line_refunds = [row.total_refunded for row in returns]

    assert line_refunds == [Decimal("6.67"), Decimal("6.66"), Decimal("6.67")]
    assert sum(line_refunds, Decimal("0.00")) == sale.total == Decimal("20.00")
    assert sum((row.discount_refunded for row in returns), Decimal("0.00")) == Decimal("0.00")
    assert svc.sale_summary(sale.id)["net_total"] == Decimal("0.00")
    assert svc.get_product(product.id).stock_current == 3


def test_global_discount_cent_rounding_is_exact_after_three_partial_returns():
    svc = service()
    product = add_stock(svc, sku="RET-GLOBAL-CENTS", unit_sale_price="100.00", quantity=3)
    sale = svc.register_sale(
        items=[{"product_id": product.id, "quantity": 3, "unit_sale_price": "100.00"}],
        discount="1.00",
    )

    returns = [return_one(svc, sale.id, f"Unidad {index}") for index in range(1, 4)]

    assert [row.discount_refunded for row in returns] == [
        Decimal("0.33"), Decimal("0.34"), Decimal("0.33")
    ]
    assert [row.total_refunded for row in returns] == [
        Decimal("99.67"), Decimal("99.66"), Decimal("99.67")
    ]
    assert sum((row.discount_refunded for row in returns), Decimal("0.00")) == sale.discount
    assert sum((row.total_refunded for row in returns), Decimal("0.00")) == sale.total


def test_cancellation_after_partial_return_uses_same_discount_reconciliation():
    svc = service()
    product = add_stock(svc, sku="RET-CANCEL-DISC", unit_sale_price="100.00", quantity=2)
    sale = svc.register_sale(
        items=[{"product_id": product.id, "quantity": 2, "unit_sale_price": "100.00"}],
        discount="20.00",
    )

    first = return_one(svc, sale.id, "Primera unidad")
    cancelled = svc.cancel_sale(sale_id=sale.id, reason="Cancelar el resto")
    summary = svc.sale_summary(sale.id)
    all_returns = svc.get_sale(sale.id).returns

    assert first.total_refunded == Decimal("90.00")
    assert sum((row.total_refunded for row in all_returns), Decimal("0.00")) == sale.total
    assert sum((row.discount_refunded for row in all_returns), Decimal("0.00")) == sale.discount
    assert summary["net_total"] == Decimal("0.00")
    assert summary["current_profit"] == Decimal("0.00")
    assert summary["status"] == "CANCELADA"
    assert cancelled.status == "CANCELADA"
    assert svc.get_product(product.id).stock_current == 2


def test_duplicate_requested_rows_cannot_over_return_or_mutate_inventory():
    svc = service()
    product = add_stock(svc, sku="RET-DUPLICATE", unit_sale_price="25.00", quantity=2)
    sale = svc.register_sale(items=[{"product_id": product.id, "quantity": 2, "unit_sale_price": "25.00"}])
    current = svc.get_sale(sale.id)
    sale_item_id = current.items[0].id

    with pytest.raises(ValidationError, match="Solo quedan 2"):
        svc.return_sale(
            sale_id=sale.id,
            items=[
                {"sale_item_id": sale_item_id, "quantity": 2},
                {"sale_item_id": sale_item_id, "quantity": 1},
            ],
            reason="Intento duplicado",
        )

    refreshed = svc.get_sale(sale.id)
    assert refreshed.items[0].returned_quantity == 0
    assert refreshed.returns == []
    assert svc.get_product(product.id).stock_current == 0
    assert not any(movement.movement_type == "DEVOLUCION" for movement in svc.movements(product.id, limit=100))


def test_store_facade_calculates_effective_sale_values_through_return_service():
    svc = service()
    product = add_stock(svc, sku="RET-EFFECTIVE", unit_sale_price="100.00", quantity=2)
    sale = svc.register_sale(items=[{"product_id": product.id, "quantity": 2, "unit_sale_price": "100.00"}])
    return_one(svc, sale.id)

    refreshed_sale = svc.get_sale(sale.id)
    effective_total, effective_profit = svc.effective_sale_values(refreshed_sale)
    summary = svc.sale_summary(sale.id)

    assert effective_total == summary["net_total"] == Decimal("100.00")
    assert effective_profit == summary["current_profit"] == Decimal("60.00")


@pytest.mark.parametrize(
    ("unit_price", "quantity", "line_discount", "global_discount"),
    [
        ("100.00", 2, "0.00", "20.00"),
        ("10.00", 3, "10.00", "0.00"),
        ("9.99", 7, "4.03", "11.11"),
        ("0.10", 6, "0.01", "0.05"),
        ("99.99", 5, "33.33", "12.35"),
    ],
)
def test_split_returns_reconcile_original_amount_for_varied_prices_and_discounts(
    unit_price: str,
    quantity: int,
    line_discount: str,
    global_discount: str,
):
    svc = service()
    product = add_stock(
        svc,
        sku=f"RET-GRID-{unit_price}-{quantity}".replace(".", ""),
        unit_sale_price=unit_price,
        quantity=quantity,
        unit_cost="0.01",
    )
    sale = svc.register_sale(
        items=[
            {
                "product_id": product.id,
                "quantity": quantity,
                "unit_sale_price": unit_price,
                "discount": line_discount,
            }
        ],
        discount=global_discount,
    )

    returns = [return_one(svc, sale.id, f"Devolución {index}") for index in range(1, quantity + 1)]

    assert all(row.total_refunded >= Decimal("0.00") for row in returns)
    assert sum((row.total_refunded for row in returns), Decimal("0.00")) == sale.total
    assert sum((row.discount_refunded for row in returns), Decimal("0.00")) == sale.discount
    assert svc.sale_summary(sale.id)["net_total"] == Decimal("0.00")
    assert svc.get_product(product.id).stock_current == quantity
