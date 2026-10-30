from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.calculations.financial import money, pct
from app.models import (
    AuditLog,
    Expense,
    InventoryLayer,
    Product,
    Purchase,
    Sale,
    SaleItem,
    SaleReturn,
)

from .definitions import REPORT_BY_KEY, ReportColumn, ReportDefinition

ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class ReportResult:
    definition: ReportDefinition
    start: datetime | None
    end: datetime | None
    rows: tuple[dict[str, Any], ...]
    generated_at: datetime
    summary: tuple[tuple[str, Any, str], ...]

    @property
    def total_rows(self) -> int:
        return len(self.rows)

    @property
    def columns(self) -> tuple[ReportColumn, ...]:
        return self.definition.columns


class ReportService:
    """Read-only report builder. No Qt/imports from the presentation layer."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def definitions(self) -> tuple[ReportDefinition, ...]:
        return tuple(REPORT_BY_KEY.values())

    @staticmethod
    def _period_bounds(period: str, now: datetime) -> tuple[datetime, datetime]:
        end = now
        today = datetime(now.year, now.month, now.day)
        key = (period or "month").lower()
        if key == "today":
            return today, end
        if key == "7d":
            return today - timedelta(days=6), end
        if key == "30d":
            return today - timedelta(days=29), end
        if key == "90d":
            return today - timedelta(days=89), end
        if key == "year":
            return datetime(now.year, 1, 1), end
        if key == "previous_month":
            first_current = datetime(now.year, now.month, 1)
            last_previous = first_current - timedelta(seconds=1)
            return datetime(last_previous.year, last_previous.month, 1), last_previous.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
        if key == "all":
            return datetime(2000, 1, 1), end
        return datetime(now.year, now.month, 1), end

    def period_bounds(
        self,
        *,
        period: str = "month",
        start: datetime | None = None,
        end: datetime | None = None,
        now: datetime | None = None,
    ) -> tuple[datetime | None, datetime | None]:
        if (start is None) != (end is None):
            raise ValueError("start y end deben proporcionarse juntos.")
        if start is not None:
            if start > end:  # type: ignore[operator]
                raise ValueError("El rango del reporte no es válido.")
            return start, end
        return self._period_bounds(period, now or datetime.now())

    def build(
        self,
        report_key: str,
        *,
        period: str = "month",
        start: datetime | None = None,
        end: datetime | None = None,
        now: datetime | None = None,
    ) -> ReportResult:
        definition = REPORT_BY_KEY.get(report_key)
        if definition is None:
            raise ValueError(f"Reporte desconocido: {report_key}")

        if definition.date_filtered:
            range_start, range_end = self.period_bounds(period=period, start=start, end=end, now=now)
        else:
            range_start = range_end = None

        builders = {
            "sales": self._sales,
            "purchases": self._purchases,
            "inventory": self._inventory,
            "profitability": self._profitability,
            "expenses": self._expenses,
            "returns": self._returns,
            "cancellations": self._cancellations,
            "audit": self._audit,
        }
        rows, summary = builders[report_key](range_start, range_end)
        return ReportResult(
            definition=definition,
            start=range_start,
            end=range_end,
            rows=tuple(rows),
            generated_at=datetime.now(),
            summary=tuple(summary),
        )

    @staticmethod
    def _in_range(value: datetime | None, start: datetime | None, end: datetime | None) -> bool:
        return value is not None and (start is None or value >= start) and (end is None or value <= end)

    @staticmethod
    def _effective_sale(sale: Sale) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        refunded = sum((r.total_refunded for r in (sale.returns or [])), ZERO)
        cogs_returned = sum((r.cogs_returned for r in (sale.returns or [])), ZERO)
        profit_impact = sum((r.profit_impact for r in (sale.returns or [])), ZERO)
        net_total = money(sale.total - refunded)
        effective_cogs = money(sale.cogs - cogs_returned)
        gross = money(sale.gross_profit - refunded + cogs_returned)
        net_profit = money(sale.net_profit - profit_impact)
        return net_total, effective_cogs, gross, net_profit

    @staticmethod
    def _total_sale_items(sale: Sale) -> int:
        return sum(int(item.quantity or 0) for item in sale.items)

    def _load_sales(self, start: datetime | None, end: datetime | None) -> list[Sale]:
        with self.session_factory() as session:
            stmt = select(Sale).options(
                selectinload(Sale.items),
                selectinload(Sale.returns).selectinload(SaleReturn.items),
            ).order_by(Sale.sale_date.desc(), Sale.id.desc())
            rows = list(session.scalars(stmt).all())
        return [sale for sale in rows if self._in_range(sale.sale_date, start, end)]

    def _sales(self, start: datetime | None, end: datetime | None) -> tuple[list[dict[str, Any]], list[tuple[str, Any, str]]]:
        sales = self._load_sales(start, end)
        rows: list[dict[str, Any]] = []
        totals = {"original": ZERO, "refunded": ZERO, "net": ZERO, "cogs": ZERO, "gross": ZERO, "profit": ZERO}
        for sale in sales:
            refunded = money(sum((r.total_refunded for r in (sale.returns or [])), ZERO))
            net_total, cogs, gross, net_profit = self._effective_sale(sale)
            totals["original"] = money(totals["original"] + sale.total)
            totals["refunded"] = money(totals["refunded"] + refunded)
            totals["net"] = money(totals["net"] + net_total)
            totals["cogs"] = money(totals["cogs"] + cogs)
            totals["gross"] = money(totals["gross"] + gross)
            totals["profit"] = money(totals["profit"] + net_profit)
            rows.append({
                "date": sale.sale_date,
                "number": sale.number,
                "status": sale.status,
                "customer": sale.customer_name or "—",
                "payment_method": sale.payment_method or "—",
                "items": self._total_sale_items(sale),
                "subtotal": sale.subtotal,
                "discount": sale.discount,
                "shipping": sale.shipping_charge,
                "original_total": sale.total,
                "refunded": refunded,
                "net_total": net_total,
                "cogs": cogs,
                "gross_profit": gross,
                "net_profit": net_profit,
            })
        summary = (
            ("Operaciones", len(rows), "integer"),
            ("Ventas netas", totals["net"], "money"),
            ("COGS", totals["cogs"], "money"),
            ("Ganancia neta", totals["profit"], "money"),
        )
        return rows, summary

    def _purchases(self, start: datetime | None, end: datetime | None) -> tuple[list[dict[str, Any]], list[tuple[str, Any, str]]]:
        with self.session_factory() as session:
            purchases = list(session.scalars(
                select(Purchase)
                .options(selectinload(Purchase.items))
                .order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
            ).all())
        purchases = [p for p in purchases if self._in_range(p.purchase_date, start, end)]
        rows = []
        total = ZERO
        for purchase in purchases:
            total = money(total + purchase.total)
            rows.append({
                "date": purchase.purchase_date,
                "number": purchase.number,
                "supplier": purchase.supplier or "—",
                "items": sum(int(item.quantity or 0) for item in purchase.items),
                "subtotal": purchase.subtotal,
                "shipping": purchase.shipping_cost,
                "other_cost": purchase.other_cost,
                "total": purchase.total,
            })
        return rows, (("Compras", len(rows), "integer"), ("Total compras", total, "money"))

    def _inventory(self, start: datetime | None, end: datetime | None) -> tuple[list[dict[str, Any]], list[tuple[str, Any, str]]]:
        del start, end
        with self.session_factory() as session:
            products = list(session.scalars(select(Product).order_by(Product.name.asc(), Product.id.asc())).all())
            value_by_product = dict(session.execute(
                select(InventoryLayer.product_id, func.coalesce(func.sum(InventoryLayer.remaining_quantity * InventoryLayer.unit_cost), 0))
                .group_by(InventoryLayer.product_id)
            ).all())
            qty_by_product = dict(session.execute(
                select(InventoryLayer.product_id, func.coalesce(func.sum(InventoryLayer.remaining_quantity), 0))
                .group_by(InventoryLayer.product_id)
            ).all())
        rows = []
        units = 0
        value = ZERO
        for product in products:
            stock = int(product.stock_current or 0)
            inventory_value = money(value_by_product.get(product.id, 0) or 0)
            layer_qty = int(qty_by_product.get(product.id, 0) or 0)
            if layer_qty > 0:
                unit_cost = money(inventory_value / Decimal(layer_qty))
            else:
                unit_cost = ZERO
            margin = pct(money(product.sale_price - unit_cost), product.sale_price)
            units += stock
            value = money(value + inventory_value)
            if not product.active:
                status = "INACTIVO"
            elif stock == 0:
                status = "AGOTADO"
            elif stock <= int(product.stock_min or 0):
                status = "STOCK BAJO"
            else:
                status = "ACTIVO"
            rows.append({
                "sku": product.sku,
                "name": product.name,
                "category": product.category or "General",
                "brand": product.brand or "—",
                "stock": stock,
                "minimum": int(product.stock_min or 0),
                "unit_cost": unit_cost,
                "inventory_value": inventory_value,
                "sale_price": product.sale_price,
                "margin": margin,
                "status": status,
            })
        return rows, (
            ("Productos", len(rows), "integer"),
            ("Unidades", units, "integer"),
            ("Valor inventario", value, "money"),
        )

    def _profitability(self, start: datetime | None, end: datetime | None) -> tuple[list[dict[str, Any]], list[tuple[str, Any, str]]]:
        sales = self._load_sales(start, end)
        with self.session_factory() as session:
            expenses = list(session.scalars(select(Expense).order_by(Expense.expense_date.asc(), Expense.id.asc())).all())
        expenses = [e for e in expenses if self._in_range(e.expense_date, start, end) and not e.direct_sale]
        if start is None or end is None:
            return [], (("Período", "Sin rango", "text"),)
        monthly = (end - start).days > 45
        buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"sales": ZERO, "cogs": ZERO, "expenses": ZERO, "operations": 0})

        def key_for(value: datetime) -> str:
            return value.strftime("%Y-%m") if monthly else value.strftime("%Y-%m-%d")

        def label_for(key: str) -> str:
            if monthly:
                year, month = key.split("-")
                return f"{month}/{year[2:]}"
            return f"{key[8:10]}/{key[5:7]}/{key[:4]}"

        for sale in sales:
            net_total, cogs, _gross, net_profit = self._effective_sale(sale)
            key = key_for(sale.sale_date)
            bucket = buckets[key]
            bucket["sales"] = money(bucket["sales"] + net_total)
            bucket["cogs"] = money(bucket["cogs"] + cogs)
            bucket["operations"] += 1
            # ``net_profit`` already contains direct sale costs and shipping.
            bucket.setdefault("sale_profit", ZERO)
            bucket["sale_profit"] = money(bucket["sale_profit"] + net_profit)

        for expense in expenses:
            key = key_for(expense.expense_date)
            bucket = buckets[key]
            bucket["expenses"] = money(bucket["expenses"] + expense.amount)

        rows = []
        cursor = start.replace(hour=0, minute=0, second=0, microsecond=0)
        step_monthly = monthly
        while cursor <= end:
            key = cursor.strftime("%Y-%m") if step_monthly else cursor.strftime("%Y-%m-%d")
            bucket = buckets.get(key, {"sales": ZERO, "cogs": ZERO, "expenses": ZERO, "operations": 0, "sale_profit": ZERO})
            gross = money(bucket["sales"] - bucket["cogs"])
            net_profit = money(bucket.get("sale_profit", ZERO) - bucket["expenses"])
            rows.append({
                "period": label_for(key),
                "sales": money(bucket["sales"]),
                "cogs": money(bucket["cogs"]),
                "gross_profit": gross,
                "general_expenses": money(bucket["expenses"]),
                "net_profit": net_profit,
                "margin": pct(net_profit, bucket["sales"]),
                "operations": int(bucket["operations"]),
            })
            if monthly:
                cursor = (cursor.replace(day=1) + timedelta(days=32)).replace(day=1)
            else:
                cursor += timedelta(days=1)

        totals_sales = sum((row["sales"] for row in rows), ZERO)
        totals_cogs = sum((row["cogs"] for row in rows), ZERO)
        totals_expenses = sum((row["general_expenses"] for row in rows), ZERO)
        totals_profit = sum((row["net_profit"] for row in rows), ZERO)
        return rows, (
            ("Ventas netas", money(totals_sales), "money"),
            ("COGS", money(totals_cogs), "money"),
            ("Gastos generales", money(totals_expenses), "money"),
            ("Ganancia neta", money(totals_profit), "money"),
        )

    def _expenses(self, start: datetime | None, end: datetime | None) -> tuple[list[dict[str, Any]], list[tuple[str, Any, str]]]:
        with self.session_factory() as session:
            expenses = list(session.scalars(select(Expense).order_by(Expense.expense_date.desc(), Expense.id.desc())).all())
            sale_ids = {expense.sale_id for expense in expenses if expense.sale_id is not None}
            sales = {}
            if sale_ids:
                sales = {sale.id: sale.number for sale in session.scalars(select(Sale).where(Sale.id.in_(sale_ids))).all()}
        expenses = [e for e in expenses if self._in_range(e.expense_date, start, end)]
        rows = []
        total = ZERO
        for expense in expenses:
            total = money(total + expense.amount)
            rows.append({
                "date": expense.expense_date,
                "category": expense.category or "Sin categoría",
                "description": expense.description or "—",
                "type": "Venta" if expense.direct_sale else "General",
                "sale_number": sales.get(expense.sale_id, "—") if expense.sale_id else "—",
                "amount": expense.amount,
                "notes": expense.notes or "—",
            })
        return rows, (("Gastos", len(rows), "integer"), ("Total gastos", total, "money"))

    def _returns(self, start: datetime | None, end: datetime | None) -> tuple[list[dict[str, Any]], list[tuple[str, Any, str]]]:
        with self.session_factory() as session:
            returns = list(session.scalars(
                select(SaleReturn)
                .options(selectinload(SaleReturn.sale), selectinload(SaleReturn.items))
                .order_by(SaleReturn.return_date.desc(), SaleReturn.id.desc())
            ).all())
        returns = [
            r for r in returns
            if self._in_range(r.return_date, start, end)
            and not (r.reason or "").strip().lower().startswith("cancelación:")
        ]
        rows = []
        refunded = ZERO
        cogs = ZERO
        for ret in returns:
            refunded = money(refunded + ret.total_refunded)
            cogs = money(cogs + ret.cogs_returned)
            rows.append({
                "date": ret.return_date,
                "sale_number": ret.sale.number if ret.sale else "—",
                "customer": ret.sale.customer_name if ret.sale and ret.sale.customer_name else "—",
                "reason": ret.reason or "—",
                "products_refunded": ret.products_refunded,
                "discount_refunded": ret.discount_refunded,
                "shipping_refunded": ret.shipping_refunded,
                "total_refunded": ret.total_refunded,
                "cogs_returned": ret.cogs_returned,
                "profit_impact": ret.profit_impact,
                "items": sum(int(item.quantity or 0) for item in ret.items),
            })
        return rows, (
            ("Devoluciones", len(rows), "integer"),
            ("Total reembolsado", refunded, "money"),
            ("COGS devuelto", cogs, "money"),
        )

    def _cancellations(self, start: datetime | None, end: datetime | None) -> tuple[list[dict[str, Any]], list[tuple[str, Any, str]]]:
        with self.session_factory() as session:
            sales = list(session.scalars(
                select(Sale).where(Sale.status == "CANCELADA").order_by(Sale.cancelled_at.desc(), Sale.id.desc())
            ).all())
        rows = []
        total = ZERO
        for sale in sales:
            effective_date = sale.cancelled_at or sale.sale_date
            if not self._in_range(effective_date, start, end):
                continue
            total = money(total + sale.original_total)
            rows.append({
                "cancelled_at": effective_date,
                "sale_date": sale.sale_date,
                "number": sale.number,
                "customer": sale.customer_name or "—",
                "reason": sale.cancellation_reason or "—",
                "original_total": sale.original_total,
                "original_cogs": sale.original_cogs,
                "original_net_profit": sale.original_net_profit,
            })
        return rows, (("Cancelaciones", len(rows), "integer"), ("Valor original", total, "money"))

    def _audit(self, start: datetime | None, end: datetime | None) -> tuple[list[dict[str, Any]], list[tuple[str, Any, str]]]:
        with self.session_factory() as session:
            logs = list(session.scalars(
                select(AuditLog).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            ).all())
        logs = [log for log in logs if self._in_range(log.occurred_at, start, end)]
        rows = [
            {
                "date": log.occurred_at,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": int(log.entity_id or 0),
                "user": log.user_name or "—",
                "details": log.details or "—",
            }
            for log in logs
        ]
        return rows, (("Registros", len(rows), "integer"),)


def filter_rows(result: ReportResult, query: str) -> tuple[dict[str, Any], ...]:
    needle = (query or "").strip().casefold()
    if not needle:
        return result.rows
    keys = [column.key for column in result.columns]
    matches = []
    for row in result.rows:
        haystack = " ".join(str(row.get(key, "")) for key in keys).casefold()
        if needle in haystack:
            matches.append(row)
    return tuple(matches)
