"""Sales return and cancellation business operations."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.calculations.financial import money
from app.core.exceptions import ValidationError
from app.models import Sale, SaleItem, SaleReturn, SaleReturnItem
from app.services.base_service import BaseService
from app.services.constants import SALE_CANCELLED, SALE_PARTIAL_RETURN, SALE_RETURNED
from app.services.inventory_service import InventoryService

ZERO = Decimal("0.00")


class ReturnService(BaseService):
    """Owns partial/full returns and sale cancellations."""

    def __init__(self, session_factory, inventory_service: InventoryService) -> None:
        super().__init__(session_factory)
        self.inventory = inventory_service

    def return_sale(
        self,
        *,
        sale_id: int,
        items: Iterable[dict],
        reason: str,
        refund_shipping: bool = False,
        notes: str = "",
        return_date: datetime | None = None,
    ) -> SaleReturn:
        requested = list(items)
        if not requested:
            raise ValidationError("Selecciona al menos una cantidad para devolver.")
        if not reason.strip():
            raise ValidationError("El motivo de la devolución es obligatorio.")

        with self._session() as session:
            sale = self._load_sale_for_returns(session, sale_id)
            if not sale:
                raise ValidationError("Venta no encontrada.")
            if sale.status == SALE_CANCELLED:
                raise ValidationError("La venta ya está cancelada.")
            if sale.status == SALE_RETURNED:
                raise ValidationError("La venta ya está devuelta por completo.")

            return_date = return_date or datetime.now()
            ret = self._apply_return_in_session(
                session,
                sale,
                requested,
                reason=reason,
                refund_shipping=refund_shipping,
                notes=notes,
                return_date=return_date,
                target_status=None,
            )

            all_returned = bool(sale.items) and all(
                item.returned_quantity >= item.quantity for item in sale.items
            )
            if all_returned:
                sale.status = SALE_RETURNED
                sale.returned_at = return_date
            else:
                sale.status = SALE_PARTIAL_RETURN

            self._audit(
                session,
                "DEVOLVER",
                "VENTA",
                sale.id,
                f"{sale.number}; devolución={ret.id}; total_reembolsado={ret.total_refunded}; motivo={reason.strip()}",
            )
            session.commit()
            session.refresh(ret)
            return ret

    def cancel_sale(
        self,
        *,
        sale_id: int,
        reason: str,
        refund_shipping: bool = True,
        notes: str = "",
        cancel_date: datetime | None = None,
    ) -> Sale:
        if not reason.strip():
            raise ValidationError("El motivo de la cancelación es obligatorio.")

        with self._session() as session:
            sale = self._load_sale_for_returns(session, sale_id)
            if not sale:
                raise ValidationError("Venta no encontrada.")
            if sale.status == SALE_CANCELLED:
                raise ValidationError("La venta ya está cancelada.")
            if sale.status == SALE_RETURNED:
                raise ValidationError("La venta ya está devuelta por completo.")

            cancel_date = cancel_date or datetime.now()
            remaining_items = [
                {"sale_item_id": item.id, "quantity": item.quantity - item.returned_quantity}
                for item in sale.items
                if item.quantity > item.returned_quantity
            ]
            if remaining_items:
                self._apply_return_in_session(
                    session,
                    sale,
                    remaining_items,
                    reason=f"Cancelación: {reason.strip()}",
                    refund_shipping=refund_shipping,
                    notes=notes,
                    return_date=cancel_date,
                    target_status=SALE_CANCELLED,
                )
            else:
                sale.status = SALE_CANCELLED

            sale.cancelled_at = cancel_date
            sale.cancellation_reason = reason.strip()
            self._audit(session, "CANCELAR", "VENTA", sale.id, f"{sale.number}; motivo={reason.strip()}")
            session.commit()
            session.refresh(sale)
            return sale

    def effective_sale_values(self, sale: Sale) -> tuple[Decimal, Decimal]:
        """Return current net sale amount and current net profit after returns."""
        if not sale.returns:
            return money(sale.total), money(sale.net_profit)
        returned_total = sum((money(r.total_refunded) for r in sale.returns), ZERO)
        profit_impact = sum((money(r.profit_impact) for r in sale.returns), ZERO)
        return money(sale.total - returned_total), money(sale.net_profit - profit_impact)

    @staticmethod
    def _load_sale_for_returns(session, sale_id: int) -> Sale | None:
        """Load all details needed to reconcile historic return totals safely."""
        return session.scalar(
            select(Sale)
            .options(
                selectinload(Sale.items).selectinload(SaleItem.allocations),
                selectinload(Sale.returns).selectinload(SaleReturn.items),
            )
            .where(Sale.id == int(sale_id))
        )

    @staticmethod
    def _normalize_requested_items(sale: Sale, requested: list[dict]) -> list[tuple[SaleItem, int]]:
        """Validate and merge duplicate requested rows before any inventory mutation."""
        quantities_by_id: dict[int, int] = {}
        for row in requested:
            try:
                item_id = int(row["sale_item_id"])
                quantity = int(row["quantity"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValidationError("La línea de devolución o su cantidad no son válidas.") from exc
            if quantity <= 0:
                raise ValidationError("La cantidad a devolver debe ser mayor que cero.")
            quantities_by_id[item_id] = quantities_by_id.get(item_id, 0) + quantity

        items_by_id = {item.id: item for item in sale.items}
        normalized: list[tuple[SaleItem, int]] = []
        for item_id, quantity in quantities_by_id.items():
            item = items_by_id.get(item_id)
            if item is None:
                raise ValidationError("Una línea de devolución no pertenece a la venta.")
            remaining = item.quantity - item.returned_quantity
            if quantity > remaining:
                raise ValidationError(
                    f"No puedes devolver {quantity} unidades de '{item.product_name_snapshot}'. Solo quedan {remaining}."
                )
            if not item.allocations:
                raise ValidationError(
                    "Esta venta no conserva las asignaciones FIFO necesarias para una devolución exacta."
                )
            normalized.append((item, quantity))

        if not normalized:
            raise ValidationError("Selecciona al menos una cantidad para devolver.")
        return normalized

    def _apply_return_in_session(
        self,
        session,
        sale: Sale,
        requested: list[dict],
        *,
        reason: str,
        refund_shipping: bool,
        notes: str,
        return_date: datetime,
        target_status: str | None,
    ) -> SaleReturn:
        """Apply one return/cancellation using the same cent-safe financial rules."""
        normalized = self._normalize_requested_items(sale, requested)

        # Reconstruct the amount already returned for each sale line from the
        # immutable return-line history. This also makes final returns absorb
        # any historic rounding cent instead of over-refunding a customer.
        returned_base_by_item: dict[int, Decimal] = defaultdict(lambda: ZERO)
        returned_qty_by_item: dict[int, int] = defaultdict(int)
        for previous_return in sale.returns:
            for previous_item in previous_return.items:
                returned_base_by_item[previous_item.sale_item_id] += money(previous_item.product_refund)
                returned_qty_by_item[previous_item.sale_item_id] += int(previous_item.quantity)

        already_refunded_base = money(
            sum(
                (money(ret.products_refunded) + money(ret.discount_refunded) for ret in sale.returns),
                ZERO,
            )
        )
        already_discount_refunded = money(
            sum((money(ret.discount_refunded) for ret in sale.returns), ZERO)
        )
        detail_base_total = money(sum(returned_base_by_item.values(), ZERO))
        if detail_base_total != already_refunded_base:
            raise ValidationError(
                "El historial financiero de las devoluciones no coincide con sus líneas. "
                "No se puede registrar otra devolución sin revisar ese historial."
            )

        for item in sale.items:
            if returned_qty_by_item.get(item.id, 0) != item.returned_quantity:
                if item.returned_quantity or returned_qty_by_item.get(item.id, 0):
                    raise ValidationError(
                        "El historial de cantidades devueltas no coincide con el detalle de la venta. "
                        "Revisa la venta antes de continuar."
                    )

        original_products_base = money(sale.subtotal)
        remaining_products_base = money(original_products_base - already_refunded_base)
        remaining_global_discount = money(money(sale.discount) - already_discount_refunded)
        if remaining_products_base < ZERO or remaining_global_discount < ZERO:
            raise ValidationError(
                "El historial de devoluciones supera los importes originales de la venta. "
                "No se pueden calcular importes seguros."
            )

        planned_lines: list[tuple[SaleItem, int, Decimal]] = []
        base_total = ZERO
        for item, quantity in normalized:
            prior_quantity = item.returned_quantity
            remaining_quantity = item.quantity - prior_quantity
            prior_line_base = money(returned_base_by_item.get(item.id, ZERO))
            original_line_base = money(item.line_total)
            remaining_line_base = money(original_line_base - prior_line_base)
            if remaining_line_base < ZERO:
                raise ValidationError(
                    f"El historial de devoluciones de '{item.product_name_snapshot}' supera el valor original de la línea."
                )
            if prior_quantity > 0 and item.id not in returned_base_by_item:
                raise ValidationError(
                    f"La línea '{item.product_name_snapshot}' no tiene detalle financiero de sus devoluciones anteriores."
                )

            if quantity == remaining_quantity:
                # The final units receive the exact residual, including any
                # cent caused by earlier rounding or older stored records.
                line_base = remaining_line_base
            else:
                cumulative_quantity = prior_quantity + quantity
                cumulative_target = money(
                    original_line_base * Decimal(cumulative_quantity) / Decimal(item.quantity)
                )
                line_base = money(cumulative_target - prior_line_base)
                # Defensive fallback for legacy histories whose individual
                # rounded lines differ by one cent from the new allocation.
                if line_base < ZERO or line_base > remaining_line_base:
                    line_base = money(
                        remaining_line_base * Decimal(quantity) / Decimal(remaining_quantity)
                    )

            if line_base < ZERO or line_base > remaining_line_base:
                raise ValidationError(
                    f"No se pudo calcular un reembolso válido para '{item.product_name_snapshot}'."
                )
            planned_lines.append((item, quantity, line_base))
            base_total += line_base

        base_total = money(base_total)
        if base_total > remaining_products_base:
            raise ValidationError(
                "El importe solicitado supera el valor pendiente de devolver de la venta."
            )

        # Allocate the global discount cumulatively against the original base.
        # Repeated returns therefore add up to the exact original discount;
        # the last return receives the residual cents.
        if original_products_base == ZERO:
            discount_refund = ZERO
        elif base_total >= remaining_products_base:
            discount_refund = remaining_global_discount
        else:
            cumulative_refund_base = money(already_refunded_base + base_total)
            cumulative_discount_target = money(
                money(sale.discount) * cumulative_refund_base / original_products_base
            )
            discount_refund = money(cumulative_discount_target - already_discount_refunded)
            if discount_refund < ZERO:
                raise ValidationError("El historial de descuentos devueltos no es coherente con la venta.")
            discount_refund = min(discount_refund, remaining_global_discount)

        products_refunded = money(base_total - discount_refund)
        if products_refunded < ZERO:
            raise ValidationError("El descuento asignado supera el importe de los productos devueltos.")

        original_shipping_charge = money(sale.shipping_charge)
        already_shipping_refunded = money(sale.shipping_refunded)
        remaining_shipping_charge = money(original_shipping_charge - already_shipping_refunded)
        if remaining_shipping_charge < ZERO:
            raise ValidationError("El historial de reembolsos del domicilio supera el cobro original.")
        shipping_refunded = remaining_shipping_charge if refund_shipping else ZERO
        total_refunded = money(products_refunded + shipping_refunded)
        if total_refunded < ZERO:
            raise ValidationError("El reembolso calculado no puede ser negativo.")

        # Only mutate stock after all requested quantities and monetary limits
        # have passed validation. SQLAlchemy rolls the transaction back if a
        # FIFO restoration fails before commit.
        total_cogs_returned = ZERO
        persisted_lines: list[tuple[SaleItem, int, Decimal, Decimal]] = []
        for item, quantity, line_base in planned_lines:
            cogs = money(self.inventory.restore_fifo_for_return(session, sale, item, quantity, return_date))
            item.returned_quantity += quantity
            total_cogs_returned += cogs
            persisted_lines.append((item, quantity, line_base, cogs))

        total_cogs_returned = money(total_cogs_returned)
        sale.shipping_refunded = money(already_shipping_refunded + shipping_refunded)
        ret = SaleReturn(
            sale_id=sale.id,
            return_date=return_date,
            reason=reason.strip(),
            products_refunded=products_refunded,
            discount_refunded=discount_refund,
            shipping_refunded=shipping_refunded,
            total_refunded=total_refunded,
            cogs_returned=total_cogs_returned,
            profit_impact=money(products_refunded + shipping_refunded - total_cogs_returned),
            notes=notes.strip(),
        )
        session.add(ret)
        session.flush()
        for item, quantity, line_base, cogs in persisted_lines:
            session.add(
                SaleReturnItem(
                    sale_return_id=ret.id,
                    sale_item_id=item.id,
                    quantity=quantity,
                    product_refund=money(line_base),
                    cogs_returned=money(cogs),
                )
            )

        if target_status is not None:
            sale.status = target_status
        return ret
