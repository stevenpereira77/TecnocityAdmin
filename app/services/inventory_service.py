"""Inventory and FIFO cost-flow operations."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.calculations.financial import money
from app.core.exceptions import InsufficientStockError, ValidationError
from app.models import InventoryLayer, InventoryMovement, Product, Sale, SaleItem
from app.services.base_service import BaseService


class InventoryService(BaseService):
    """Owns inventory quantities, layers, movements and FIFO allocations."""

    def add_layer(
        self,
        session: Session,
        *,
        product_id: int,
        purchase_item_id: int | None,
        received_at: datetime,
        quantity: int,
        unit_cost,
    ) -> InventoryLayer:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValidationError("La cantidad de una capa de inventario debe ser mayor que cero.")
        layer = InventoryLayer(
            product_id=int(product_id),
            purchase_item_id=purchase_item_id,
            received_at=received_at,
            original_quantity=quantity,
            remaining_quantity=quantity,
            unit_cost=money(unit_cost),
        )
        session.add(layer)
        session.flush()
        return layer

    def consume_fifo_allocations(
        self,
        session: Session,
        product: Product,
        quantity: int,
    ) -> tuple[Decimal, list[tuple[int, int, Decimal]]]:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValidationError("La cantidad FIFO debe ser mayor que cero.")

        remaining = quantity
        cost = Decimal("0.00")
        allocations: list[tuple[int, int, Decimal]] = []
        layers = list(
            session.scalars(
                select(InventoryLayer)
                .where(
                    InventoryLayer.product_id == product.id,
                    InventoryLayer.remaining_quantity > 0,
                )
                .order_by(InventoryLayer.received_at, InventoryLayer.id)
            ).all()
        )
        available = sum(x.remaining_quantity for x in layers)
        if available < quantity:
            raise InsufficientStockError(f"Stock insuficiente para '{product.name}'.")

        for layer in layers:
            if remaining <= 0:
                break
            take = min(remaining, layer.remaining_quantity)
            cost += layer.unit_cost * take
            layer.remaining_quantity -= take
            allocations.append((layer.id, take, money(layer.unit_cost)))
            remaining -= take

        return money(cost), allocations

    def consume_fifo(self, session: Session, product: Product, quantity: int) -> Decimal:
        cost, _ = self.consume_fifo_allocations(session, product, quantity)
        return cost

    def estimate_fifo_cost(self, session: Session, product: Product, quantity: int) -> Decimal:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValidationError("La cantidad FIFO debe ser mayor que cero.")
        remaining = quantity
        cost = Decimal("0.00")
        layers = list(
            session.scalars(
                select(InventoryLayer)
                .where(
                    InventoryLayer.product_id == product.id,
                    InventoryLayer.remaining_quantity > 0,
                )
                .order_by(InventoryLayer.received_at, InventoryLayer.id)
            ).all()
        )
        available = sum(x.remaining_quantity for x in layers)
        if available < quantity:
            raise InsufficientStockError(f"Stock insuficiente para '{product.name}'.")
        for layer in layers:
            if remaining <= 0:
                break
            take = min(remaining, layer.remaining_quantity)
            cost += layer.unit_cost * take
            remaining -= take
        return money(cost)

    def restore_fifo_for_return(
        self,
        session: Session,
        sale: Sale,
        sale_item: SaleItem,
        quantity: int,
        return_date: datetime,
    ) -> Decimal:
        quantity = int(quantity)
        if quantity <= 0:
            raise ValidationError("La cantidad a devolver debe ser mayor que cero.")

        remaining = quantity
        returned_cost = Decimal("0.00")
        allocations = sorted(sale_item.allocations, key=lambda x: x.id)
        for allocation in allocations:
            available = allocation.quantity - allocation.returned_quantity
            if available <= 0:
                continue
            take = min(remaining, available)
            returned_cost += allocation.unit_cost * take
            allocation.returned_quantity += take

            source_layer = session.get(InventoryLayer, allocation.inventory_layer_id)
            self.add_layer(
                session,
                product_id=sale_item.product_id,
                purchase_item_id=source_layer.purchase_item_id if source_layer else None,
                received_at=return_date,
                quantity=take,
                unit_cost=allocation.unit_cost,
            )

            product = session.get(Product, sale_item.product_id)
            if not product:
                raise ValidationError("Producto de devolución no encontrado.")
            product.stock_current += take
            session.add(
                InventoryMovement(
                    product_id=product.id,
                    movement_type="DEVOLUCION",
                    quantity=take,
                    occurred_at=return_date,
                    document_type="VENTA",
                    document_id=sale.id,
                    reason="Entrada por devolución/cancelación",
                    user_name="admin",
                    notes=f"{sale.number}; producto {sale_item.product_name_snapshot}",
                )
            )
            remaining -= take
            if remaining == 0:
                break

        if remaining != 0:
            raise ValidationError("No fue posible reconstruir el costo FIFO de la devolución; la operación fue cancelada.")
        return money(returned_cost)

    def adjust_stock(self, *, product_id: int, quantity: int, reason: str, notes: str = "") -> None:
        quantity = int(quantity)
        if quantity == 0:
            raise ValidationError("El ajuste debe ser distinto de cero.")
        if not reason.strip():
            raise ValidationError("El motivo del ajuste es obligatorio.")

        with self._session() as session:
            product = session.get(Product, int(product_id))
            if not product:
                raise ValidationError("Producto no encontrado.")
            if product.stock_current + quantity < 0:
                raise ValidationError("El ajuste dejaría el stock por debajo de cero.")

            product.stock_current += quantity
            if quantity > 0:
                current_value = session.scalar(
                    select(
                        func.coalesce(
                            func.sum(InventoryLayer.remaining_quantity * InventoryLayer.unit_cost),
                            0,
                        )
                    ).where(InventoryLayer.product_id == product.id)
                ) or 0
                current_qty = session.scalar(
                    select(func.coalesce(func.sum(InventoryLayer.remaining_quantity), 0)).where(
                        InventoryLayer.product_id == product.id
                    )
                ) or 0
                unit_cost = money(current_value / current_qty) if current_qty else Decimal("0.00")
                self.add_layer(
                    session,
                    product_id=product.id,
                    purchase_item_id=None,
                    received_at=datetime.now(),
                    quantity=quantity,
                    unit_cost=unit_cost,
                )
            else:
                self.consume_fifo(session, product, abs(quantity))

            session.add(
                InventoryMovement(
                    product_id=product.id,
                    movement_type="AJUSTE_POSITIVO" if quantity > 0 else "AJUSTE_NEGATIVO",
                    quantity=quantity,
                    reason=reason.strip(),
                    user_name="admin",
                    notes=notes.strip(),
                )
            )
            self._audit(session, "AJUSTAR_STOCK", "PRODUCTO", product.id, f"cantidad={quantity}; motivo={reason.strip()}")
            session.commit()

    def inventory_rows(self, *, limit: int | None = None, offset: int = 0) -> list[dict]:
        """Return inventory rows in one aggregate query (no N+1 layer queries)."""
        with self._session() as session:
            value_subquery = (
                select(
                    InventoryLayer.product_id.label("product_id"),
                    func.coalesce(func.sum(InventoryLayer.remaining_quantity * InventoryLayer.unit_cost), 0).label("value"),
                )
                .group_by(InventoryLayer.product_id)
                .subquery("inventory_values")
            )
            stmt = (
                select(Product, func.coalesce(value_subquery.c.value, 0).label("inventory_value"))
                .outerjoin(value_subquery, value_subquery.c.product_id == Product.id)
                .order_by(Product.name.asc(), Product.id.asc())
            )
            if limit is not None:
                stmt = stmt.limit(max(1, min(int(limit), 500))).offset(max(0, int(offset)))
            rows = session.execute(stmt).all()
            result = []
            for product, value in rows:
                stock = int(product.stock_current or 0)
                result.append({
                    "id": product.id,
                    "sku": product.sku,
                    "name": product.name,
                    "image_thumbnail_data": bytes(product.image_thumbnail_data) if product.image_thumbnail_data else None,
                    "image_path": product.image_path or "",
                    "stock": stock,
                    "minimum": int(product.stock_min or 0),
                    "value": money(value or 0),
                    "status": "AGOTADO" if stock == 0 else ("BAJO" if stock <= int(product.stock_min or 0) else "OK"),
                })
            return result

    def inventory_count(self) -> int:
        with self._session() as session:
            return int(session.scalar(select(func.count(Product.id))) or 0)

    def movements(self, product_id: int | None = None, limit: int = 100) -> list[InventoryMovement]:
        with self._session() as session:
            stmt = (
                select(InventoryMovement)
                .options(joinedload(InventoryMovement.product))
                .order_by(InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc())
            )
            if product_id:
                stmt = stmt.where(InventoryMovement.product_id == int(product_id))
            stmt = stmt.limit(max(1, min(int(limit), 500)))
            return list(session.scalars(stmt).all())
