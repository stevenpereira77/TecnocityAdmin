"""Sales, returns and delivery business operations."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.calculations.financial import line_total, money, sale_financials
from app.core.exceptions import InsufficientStockError, ValidationError
from app.models import (
    InventoryMovement,
    Product,
    Sale,
    SaleItem,
    SaleLayerAllocation,
    SaleReturn,
    SaleReturnItem,
)
from app.services.base_service import BaseService
from app.services.constants import (
    DELIVERY_STATUSES,
    SALE_CANCELLED,
    SALE_CONFIRMED,
    SALE_INACTIVE,
    SALE_PARTIAL_RETURN,
    SALE_RETURNED,
    SHIPPING_CUSTOMER_DIRECT,
    SHIPPING_CUSTOMER_ORDER,
    SHIPPING_PAYER_LABELS,
    SHIPPING_STORE,
)
from app.services.inventory_service import InventoryService


def shipping_expense(shipping_cost: Decimal, shipping_payer: str) -> Decimal:
    """Return the portion of delivery cost paid by Tecnocity."""
    return money(shipping_cost) if shipping_payer in {SHIPPING_STORE, SHIPPING_CUSTOMER_ORDER} else Decimal("0.00")


class SaleService(BaseService):
    """Owns sales, sale previews, delivery states, returns and cancellations."""

    def __init__(self, session_factory, inventory_service: InventoryService) -> None:
        super().__init__(session_factory)
        self.inventory = inventory_service

    def register_sale(
        self,
        *,
        items: Iterable[dict],
        discount=0,
        shipping_cost=0,
        shipping_charge=0,
        shipping_payer: str = SHIPPING_STORE,
        commission=0,
        other_cost=0,
        payment_method="Efectivo",
        notes="",
        customer_name="",
        customer_phone="",
        customer_address="",
        delivery_status: str = "PENDIENTE",
        sale_date: datetime | None = None,
    ) -> Sale:
        items = list(items)
        if not items:
            raise ValidationError("La venta debe tener al menos un producto.")
        self._validate_sale_shipping(shipping_payer, shipping_charge)
        if delivery_status not in DELIVERY_STATUSES:
            raise ValidationError("El estado de entrega no es válido.")

        discount = money(discount)
        shipping = money(shipping_cost)
        shipping_charge = money(shipping_charge)
        commission = money(commission)
        other = money(other_cost)
        self._ensure_non_negative(discount, shipping, shipping_charge, commission, other)

        with self._session() as session:
            normalized = []
            subtotal = Decimal("0.00")
            requested_by_product: dict[int, int] = {}
            for item in items:
                product = session.get(Product, int(item["product_id"]))
                if not product or not product.active:
                    raise ValidationError("Producto inexistente o inactivo.")
                qty = int(item["quantity"])
                if qty <= 0:
                    raise ValidationError("La cantidad debe ser mayor que cero.")
                requested_by_product[product.id] = requested_by_product.get(product.id, 0) + qty
                price = money(item.get("unit_sale_price", product.sale_price))
                if price < 0:
                    raise ValidationError("El precio de venta no puede ser negativo.")
                line_discount = money(item.get("discount", 0))
                line = line_total(price, qty, line_discount)
                if line < 0:
                    raise ValidationError("El descuento de una línea no puede superar su importe.")
                normalized.append((product, qty, price, line_discount, line))
                subtotal += line

            for product_id, requested in requested_by_product.items():
                product = session.get(Product, product_id)
                if product.stock_current < requested:
                    raise InsufficientStockError(
                        f"No hay suficiente stock para '{product.name}'. Disponible: {product.stock_current}."
                    )

            subtotal = money(subtotal)
            products_revenue = money(subtotal - discount)
            if products_revenue < 0:
                raise ValidationError("El descuento global no puede superar el subtotal.")

            number = self._next_document_number(session, "V")
            sale = Sale(
                number=number,
                sale_date=sale_date or datetime.now(),
                discount=discount,
                shipping_cost=shipping,
                shipping_charge=shipping_charge,
                shipping_payer=shipping_payer,
                shipping_refunded=Decimal("0.00"),
                commission=commission,
                other_cost=other,
                payment_method=payment_method.strip() or "Efectivo",
                subtotal=subtotal,
                total=money(products_revenue + shipping_charge),
                status=SALE_CONFIRMED,
                delivery_status=delivery_status,
                customer_name=customer_name.strip(),
                customer_phone=customer_phone.strip(),
                customer_address=customer_address.strip(),
                notes=notes.strip(),
            )
            session.add(sale)
            session.flush()

            total_cogs = Decimal("0.00")
            for product, qty, price, line_discount, line in normalized:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    sku_snapshot=product.sku,
                    product_name_snapshot=product.name,
                    quantity=qty,
                    unit_sale_price=price,
                    discount=line_discount,
                    line_total=line,
                    cogs=Decimal("0.00"),
                )
                session.add(sale_item)
                session.flush()

                cost, allocations = self.inventory.consume_fifo_allocations(session, product, qty)
                total_cogs += cost
                sale_item.cogs = money(cost)
                for layer_id, take, unit_cost in allocations:
                    session.add(
                        SaleLayerAllocation(
                            sale_id=sale.id,
                            sale_item_id=sale_item.id,
                            inventory_layer_id=layer_id,
                            quantity=take,
                            returned_quantity=0,
                            unit_cost=unit_cost,
                        )
                    )
                product.stock_current -= qty
                session.add(
                    InventoryMovement(
                        product_id=product.id,
                        movement_type="VENTA",
                        quantity=-qty,
                        occurred_at=sale.sale_date,
                        document_type="VENTA",
                        document_id=sale.id,
                        reason="Salida por venta",
                        user_name="admin",
                        notes=sale.number,
                    )
                )

            total_cogs = money(total_cogs)
            financials = sale_financials(
                subtotal,
                discount,
                shipping_charge,
                total_cogs,
                shipping,
                shipping_payer,
                commission,
                other,
            )
            sale.cogs = total_cogs
            sale.gross_profit = financials["gross_profit"]
            sale.net_profit = financials["net_profit"]
            sale.original_subtotal = subtotal
            sale.original_total = financials["total"]
            sale.original_cogs = total_cogs
            sale.original_gross_profit = financials["gross_profit"]
            sale.original_net_profit = financials["net_profit"]
            sale.total = financials["total"]

            self._audit(
                session,
                "CREAR",
                "VENTA",
                sale.id,
                f"{sale.number}; total={sale.total}; costo={sale.cogs}; utilidad={sale.net_profit}; domicilio={shipping_payer}",
            )
            session.commit()
            session.refresh(sale)
            return sale

    def preview_sale(
        self,
        *,
        items: Iterable[dict],
        discount=0,
        shipping_cost=0,
        shipping_charge=0,
        shipping_payer: str = SHIPPING_STORE,
        commission=0,
        other_cost=0,
    ) -> dict:
        items = list(items)
        if not items:
            return {
                "line_totals": [],
                "subtotal": Decimal("0.00"),
                "total": Decimal("0.00"),
                "cogs": Decimal("0.00"),
                "gross_profit": Decimal("0.00"),
                "net_profit": Decimal("0.00"),
            }

        discount = money(discount)
        shipping = money(shipping_cost)
        shipping_charge = money(shipping_charge)
        commission = money(commission)
        other = money(other_cost)
        self._ensure_non_negative(discount, shipping, shipping_charge, commission, other)
        self._validate_sale_shipping(shipping_payer, shipping_charge)

        with self._session() as session:
            subtotal = Decimal("0.00")
            line_totals = []
            total_cogs = Decimal("0.00")
            requested: dict[int, int] = {}
            normalized = []

            for item in items:
                product = session.get(Product, int(item["product_id"]))
                if not product or not product.active:
                    raise ValidationError("Producto inexistente o inactivo.")
                qty = int(item["quantity"])
                if qty <= 0:
                    raise ValidationError("La cantidad debe ser mayor que cero.")
                price = money(item.get("unit_sale_price", product.sale_price))
                if price < 0:
                    raise ValidationError("El precio de venta no puede ser negativo.")
                line_discount = money(item.get("discount", 0))
                line = line_total(price, qty, line_discount)
                if line < 0:
                    raise ValidationError("El descuento de una línea no puede superar su importe.")
                requested[product.id] = requested.get(product.id, 0) + qty
                normalized.append((product, qty, price, line_discount, line))
                subtotal += line
                line_totals.append(line)

            for product_id, qty in requested.items():
                product = session.get(Product, product_id)
                if product.stock_current < qty:
                    raise InsufficientStockError(
                        f"No hay suficiente stock para '{product.name}'. Disponible: {product.stock_current}."
                    )

            for product, qty, *_ in normalized:
                total_cogs += self.inventory.estimate_fifo_cost(session, product, qty)

            financials = sale_financials(
                money(subtotal),
                discount,
                shipping_charge,
                money(total_cogs),
                shipping,
                shipping_payer,
                commission,
                other,
            )
            return {
                "line_totals": line_totals,
                "subtotal": money(subtotal),
                "total": financials["total"],
                "cogs": money(total_cogs),
                "gross_profit": financials["gross_profit"],
                "net_profit": financials["net_profit"],
            }

    def get_sale(self, sale_id: int) -> Sale | None:
        with self._session() as session:
            stmt = (
                select(Sale)
                .options(
                    selectinload(Sale.items).selectinload(SaleItem.allocations),
                    selectinload(Sale.returns).selectinload(SaleReturn.items),
                )
                .where(Sale.id == int(sale_id))
            )
            return session.scalar(stmt)

    def get_sale_by_number(self, number: str) -> Sale | None:
        with self._session() as session:
            stmt = select(Sale).options(selectinload(Sale.items), selectinload(Sale.returns)).where(Sale.number == number)
            return session.scalar(stmt)

    def sale_summary(self, sale_id: int) -> dict:
        with self._session() as session:
            sale = session.scalar(
                select(Sale)
                .options(selectinload(Sale.items), selectinload(Sale.returns))
                .where(Sale.id == int(sale_id))
            )
            if not sale:
                raise ValidationError("Venta no encontrada.")
            returned_total = sum((r.total_refunded for r in sale.returns), Decimal("0"))
            returned_cogs = sum((r.cogs_returned for r in sale.returns), Decimal("0"))
            profit_impact = sum((r.profit_impact for r in sale.returns), Decimal("0"))
            return {
                "id": sale.id,
                "number": sale.number,
                "status": sale.status,
                "delivery_status": sale.delivery_status,
                "subtotal": money(sale.subtotal),
                "total": money(sale.total),
                "returned_total": money(returned_total),
                "net_total": money(sale.total - returned_total),
                "cogs": money(sale.cogs),
                "current_cogs": money(sale.cogs - returned_cogs),
                "net_profit": money(sale.net_profit),
                "current_profit": money(sale.net_profit - profit_impact),
                "shipping_cost": money(sale.shipping_cost),
                "shipping_charge": money(sale.shipping_charge),
                "shipping_payer": sale.shipping_payer,
                "customer_name": sale.customer_name,
                "customer_phone": sale.customer_phone,
                "customer_address": sale.customer_address,
            }

    def update_delivery_status(self, sale_id: int, delivery_status: str) -> Sale:
        if delivery_status not in DELIVERY_STATUSES:
            raise ValidationError("El estado de entrega no es válido.")
        with self._session() as session:
            sale = session.get(Sale, int(sale_id))
            if not sale:
                raise ValidationError("Venta no encontrada.")
            if sale.status in SALE_INACTIVE:
                raise ValidationError("No se puede cambiar el estado de entrega de una venta cerrada.")
            old = sale.delivery_status
            sale.delivery_status = delivery_status
            self._audit(session, "CAMBIAR_ESTADO", "VENTA", sale.id, f"entrega: {old} -> {delivery_status}")
            session.commit()
            session.refresh(sale)
            return sale

    @staticmethod
    def _ensure_non_negative(*values: Decimal) -> None:
        if any(value < 0 for value in values):
            raise ValidationError("Los descuentos, cobros y costos no pueden ser negativos.")

    @staticmethod
    def _validate_sale_shipping(shipping_payer: str, shipping_charge) -> None:
        if shipping_payer not in SHIPPING_PAYER_LABELS:
            raise ValidationError("La modalidad de domicilio seleccionada no es válida.")
        if shipping_payer != SHIPPING_CUSTOMER_ORDER and money(shipping_charge) != 0:
            raise ValidationError(
                "Solo puede cobrarse domicilio a través de Tecnocity cuando el cliente paga el domicilio en la venta."
            )
