"""Purchase business operations."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable

from app.calculations.financial import money
from app.core.exceptions import ValidationError
from app.models import InventoryMovement, Product, Purchase, PurchaseItem
from app.services.base_service import BaseService
from app.services.inventory_service import InventoryService


class PurchaseService(BaseService):
    """Creates purchases and corresponding FIFO inventory layers."""

    def __init__(self, session_factory, inventory_service: InventoryService) -> None:
        super().__init__(session_factory)
        self.inventory = inventory_service

    def register_purchase(
        self,
        *,
        supplier: str,
        items: Iterable[dict],
        shipping_cost=0,
        other_cost=0,
        notes: str = "",
        purchase_date: datetime | None = None,
    ) -> Purchase:
        items = list(items)
        if not items:
            raise ValidationError("La compra debe tener al menos un producto.")
        shipping = money(shipping_cost)
        other = money(other_cost)
        if shipping < 0 or other < 0:
            raise ValidationError("Los gastos de compra no pueden ser negativos.")

        with self._session() as session:
            normalized = []
            subtotal = Decimal("0.00")
            for item in items:
                product = session.get(Product, int(item["product_id"]))
                if not product:
                    raise ValidationError("Uno de los productos seleccionados no existe.")
                qty = int(item["quantity"])
                unit = money(item["unit_cost"])
                if qty <= 0 or unit < 0:
                    raise ValidationError("Cantidad y costo unitario deben ser válidos.")
                total = money(unit * qty)
                normalized.append((product, qty, unit, total))
                subtotal += total

            subtotal = money(subtotal)
            total = money(subtotal + shipping + other)
            number = self._next_document_number(session, "C")
            purchase = Purchase(
                number=number,
                supplier=supplier.strip(),
                purchase_date=purchase_date or datetime.now(),
                shipping_cost=shipping,
                other_cost=other,
                subtotal=subtotal,
                total=total,
                notes=notes.strip(),
            )
            session.add(purchase)
            session.flush()

            burden = money(shipping + other)
            allocated = Decimal("0.00")
            for index, (product, qty, unit, total_line) in enumerate(normalized):
                if index == len(normalized) - 1:
                    allocated_line = money(burden - allocated)
                elif subtotal == 0:
                    allocated_line = Decimal("0.00")
                else:
                    allocated_line = money(burden * (total_line / subtotal))
                allocated += allocated_line

                effective_unit = money((total_line + allocated_line) / qty)
                purchase_item = PurchaseItem(
                    purchase_id=purchase.id,
                    product_id=product.id,
                    quantity=qty,
                    unit_cost=unit,
                    line_total=total_line,
                )
                session.add(purchase_item)
                session.flush()

                self.inventory.add_layer(
                    session,
                    product_id=product.id,
                    purchase_item_id=purchase_item.id,
                    received_at=purchase.purchase_date,
                    quantity=qty,
                    unit_cost=effective_unit,
                )
                product.stock_current += qty
                session.add(
                    InventoryMovement(
                        product_id=product.id,
                        movement_type="COMPRA",
                        quantity=qty,
                        occurred_at=purchase.purchase_date,
                        document_type="COMPRA",
                        document_id=purchase.id,
                        reason="Entrada por compra",
                        user_name="admin",
                        notes=purchase.number,
                    )
                )

            self._audit(session, "CREAR", "COMPRA", purchase.id, f"{purchase.number}; total={purchase.total}")
            session.commit()
            session.refresh(purchase)
            return purchase

    def preview_purchase(self, *, items: Iterable[dict], shipping_cost=0, other_cost=0) -> dict:
        items = list(items)
        shipping = money(shipping_cost)
        other = money(other_cost)
        if shipping < 0 or other < 0:
            raise ValidationError("Los gastos de compra no pueden ser negativos.")
        subtotal = Decimal("0.00")
        line_totals = []
        for item in items:
            qty = int(item["quantity"])
            unit = money(item["unit_cost"])
            if qty <= 0 or unit < 0:
                raise ValidationError("Cantidad y costo unitario deben ser válidos.")
            total = money(unit * qty)
            subtotal += total
            line_totals.append(total)
        subtotal = money(subtotal)
        return {
            "line_totals": line_totals,
            "subtotal": subtotal,
            "total": money(subtotal + shipping + other),
        }
