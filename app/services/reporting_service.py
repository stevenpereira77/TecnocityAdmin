"""Read-oriented reporting and dashboard queries optimized for large SQLite datasets."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import asc, case, desc, func, select
from sqlalchemy.orm import selectinload

from app.calculations.financial import money, pct
from app.models import AuditLog, Expense, InventoryLayer, Product, Purchase, Sale, SaleItem, SaleReturn, SaleReturnItem
from app.services.base_service import BaseService
from app.services.sale_service import shipping_expense


ZERO = Decimal("0.00")


class ReportingService(BaseService):
    """Read-only reporting layer.

    The key scalability rule is simple: list/detail screens may load a bounded
    number of ORM objects, while dashboard metrics are calculated in SQL using
    indexed aggregation queries. Large tables are never materialized just to
    compute a count or a total.
    """

    def purchases(self, limit: int = 100) -> list[Purchase]:
        limit = max(1, min(int(limit), 1000))
        with self._session() as session:
            return list(session.scalars(select(Purchase).order_by(Purchase.purchase_date.desc(), Purchase.id.desc()).limit(limit)).all())

    def sales(self, limit: int = 100) -> list[Sale]:
        limit = max(1, min(int(limit), 1000))
        with self._session() as session:
            stmt = (
                select(Sale)
                .options(selectinload(Sale.returns))
                .order_by(Sale.sale_date.desc(), Sale.id.desc())
                .limit(limit)
            )
            return list(session.scalars(stmt).all())

    def expenses(self, limit: int = 100) -> list[Expense]:
        limit = max(1, min(int(limit), 1000))
        with self._session() as session:
            return list(session.scalars(select(Expense).order_by(Expense.expense_date.desc(), Expense.id.desc()).limit(limit)).all())

    def audit_logs(self, limit: int = 150) -> list[AuditLog]:
        limit = max(1, min(int(limit), 1000))
        with self._session() as session:
            return list(
                session.scalars(
                    select(AuditLog)
                    .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
                    .limit(limit)
                ).all()
            )

    @staticmethod
    def _effective(sale: Sale) -> tuple[Decimal, Decimal]:
        returned_total = sum((r.total_refunded for r in (sale.returns or [])), ZERO)
        profit_impact = sum((r.profit_impact for r in (sale.returns or [])), ZERO)
        return money(sale.total - returned_total), money(sale.net_profit - profit_impact)

    def period_bounds(self, period: str = "month", now: datetime | None = None) -> tuple[datetime, datetime]:
        return self._period_bounds(period, now or datetime.now())

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

    @staticmethod
    def _comparison_bounds(start: datetime, end: datetime) -> tuple[datetime, datetime]:
        duration = end - start
        previous_end = start - timedelta(microseconds=1)
        previous_start = previous_end - duration
        return previous_start, previous_end

    @staticmethod
    def _bucket_key(value: datetime, monthly: bool) -> str:
        return value.strftime("%Y-%m") if monthly else value.strftime("%Y-%m-%d")

    @staticmethod
    def _bucket_label(key: str, monthly: bool) -> str:
        if monthly:
            year, month = key.split("-")
            return f"{month}/{year[2:]}"
        return key[8:10] + "/" + key[5:7]

    @staticmethod
    def _return_totals_subquery():
        return (
            select(
                SaleReturn.sale_id.label("sale_id"),
                func.coalesce(func.sum(SaleReturn.total_refunded), 0).label("refunded"),
                func.coalesce(func.sum(SaleReturn.cogs_returned), 0).label("cogs_returned"),
                func.coalesce(func.sum(SaleReturn.profit_impact), 0).label("profit_impact"),
                func.coalesce(func.sum(SaleReturn.discount_refunded), 0).label("discount_refunded"),
            )
            .group_by(SaleReturn.sale_id)
            .subquery("sale_return_totals")
        )

    @staticmethod
    def _return_item_cogs_subquery():
        return (
            select(
                SaleReturnItem.sale_item_id.label("sale_item_id"),
                func.coalesce(func.sum(SaleReturnItem.cogs_returned), 0).label("cogs_returned"),
            )
            .group_by(SaleReturnItem.sale_item_id)
            .subquery("sale_item_return_cogs")
        )

    @classmethod
    def _effective_sale_expressions(cls, return_totals):
        refunded = func.coalesce(return_totals.c.refunded, 0)
        returned_cogs = func.coalesce(return_totals.c.cogs_returned, 0)
        profit_impact = func.coalesce(return_totals.c.profit_impact, 0)
        return (
            Sale.total - refunded,
            Sale.cogs - returned_cogs,
            Sale.net_profit - profit_impact,
        )

    @staticmethod
    def _range_clause(column, start: datetime, end: datetime):
        return column >= start, column <= end

    def _sales_summary(self, session, start: datetime, end: datetime) -> dict[str, Decimal | int]:
        returns = self._return_totals_subquery()
        net_total_expr, cogs_expr, profit_expr = self._effective_sale_expressions(returns)
        ticket_case = case((net_total_expr > 0, 1), else_=0)
        row = session.execute(
            select(
                func.coalesce(func.sum(net_total_expr), 0),
                func.coalesce(func.sum(cogs_expr), 0),
                func.coalesce(func.sum(profit_expr), 0),
                func.count(Sale.id),
                func.coalesce(func.sum(ticket_case), 0),
            )
            .select_from(Sale)
            .outerjoin(returns, returns.c.sale_id == Sale.id)
            .where(*self._range_clause(Sale.sale_date, start, end))
        ).one()
        net_sales = money(row[0] or 0)
        cogs = money(row[1] or 0)
        profit = money(row[2] or 0)
        operations = int(row[3] or 0)
        ticket_count = int(row[4] or 0)
        return {
            "sales": net_sales,
            "cogs": cogs,
            "gross_profit": money(net_sales - cogs),
            "profit": profit,
            "operations": operations,
            "ticket_count": ticket_count,
            "average_ticket": money(net_sales / ticket_count) if ticket_count else ZERO,
            "margin": pct(profit, net_sales),
        }

    @staticmethod
    def _expense_summary(session, start: datetime, end: datetime) -> dict[str, Decimal]:
        general = case((Expense.direct_sale.is_(False), Expense.amount), else_=0)
        row = session.execute(
            select(
                func.coalesce(func.sum(Expense.amount), 0),
                func.coalesce(func.sum(general), 0),
            ).where(*ReportingService._range_clause(Expense.expense_date, start, end))
        ).one()
        return {"expenses": money(row[0] or 0), "general_expenses": money(row[1] or 0)}

    def dashboard(self, now: datetime | None = None) -> dict:
        """Backward-compatible accumulated metrics without materializing history."""
        now = now or datetime.now()
        start_day = datetime(now.year, now.month, now.day)
        start_month = datetime(now.year, now.month, 1)
        with self._session() as session:
            day = self._sales_summary(session, start_day, now)
            month = self._sales_summary(session, start_month, now)
            all_time = self._sales_summary(session, datetime(2000, 1, 1), now)
            day_exp = self._expense_summary(session, start_day, now)
            month_exp = self._expense_summary(session, start_month, now)
            all_exp = self._expense_summary(session, datetime(2000, 1, 1), now)
            purchase_total = money(session.scalar(select(func.coalesce(func.sum(Purchase.total), 0))) or 0)
            inventory_value = money(
                session.scalar(select(func.coalesce(func.sum(InventoryLayer.remaining_quantity * InventoryLayer.unit_cost), 0))) or 0
            )
            products_count = int(session.scalar(select(func.count(Product.id)).where(Product.active.is_(True))) or 0)
            low = int(session.scalar(select(func.count(Product.id)).where(
                Product.active.is_(True), Product.stock_current > 0, Product.stock_current <= Product.stock_min
            )) or 0)
            out = int(session.scalar(select(func.count(Product.id)).where(Product.active.is_(True), Product.stock_current == 0)) or 0)
            shipping_store, shipping_charged = self._shipping_totals(session, datetime(2000, 1, 1), now)
            return {
                "sales_day": day["sales"],
                "sales_month": month["sales"],
                "sales_all": all_time["sales"],
                "profit_day": money(day["profit"] - day_exp["general_expenses"]),
                "profit_month": money(month["profit"] - month_exp["general_expenses"]),
                "profit_all": money(all_time["profit"] - all_exp["general_expenses"]),
                "expenses_all": all_exp["expenses"],
                "shipping_all": shipping_store,
                "shipping_charged_all": shipping_charged,
                "invested": purchase_total,
                "inventory_value": inventory_value,
                "products_count": products_count,
                "low_stock": low,
                "out_of_stock": out,
            }

    def _shipping_totals(self, session, start: datetime, end: datetime) -> tuple[Decimal, Decimal]:
        store_payers = ["TIENDA", "CLIENTE"]
        store_cost = case((Sale.shipping_payer.in_(store_payers), Sale.shipping_cost), else_=0)
        row = session.execute(
            select(
                func.coalesce(func.sum(store_cost), 0),
                func.coalesce(func.sum(Sale.shipping_charge), 0),
            ).where(*self._range_clause(Sale.sale_date, start, end))
        ).one()
        return money(row[0] or 0), money(row[1] or 0)

    def dashboard_report(
        self,
        *,
        period: str = "month",
        start: datetime | None = None,
        end: datetime | None = None,
        now: datetime | None = None,
    ) -> dict:
        """Return dashboard metrics using bounded SQL aggregates.

        The previous implementation loaded every Sale, SaleItem, SaleReturn and
        Expense into Python. This version returns only aggregated rows, so database
        size no longer scales memory use linearly.
        """
        now = now or datetime.now()
        if (start is None) != (end is None):
            raise ValueError("start y end deben proporcionarse juntos.")
        if start is None:
            start, end = self._period_bounds(period, now)
        if start > end:
            raise ValueError("El rango del dashboard no es válido.")

        previous_start, previous_end = self._comparison_bounds(start, end)
        monthly = (end - start).days > 45 or period in {"year", "all"}

        with self._session() as session:
            current_sales = self._sales_summary(session, start, end)
            previous_sales = self._sales_summary(session, previous_start, previous_end)
            current_expenses = self._expense_summary(session, start, end)
            previous_expenses = self._expense_summary(session, previous_start, previous_end)

            current_profit = money(current_sales["profit"] - current_expenses["general_expenses"])
            previous_profit = money(previous_sales["profit"] - previous_expenses["general_expenses"])
            current = {
                **current_sales,
                "general_expenses": current_expenses["general_expenses"],
                "expenses": current_expenses["expenses"],
                "profit": current_profit,
                "margin": pct(current_profit, current_sales["sales"]),
            }
            previous = {
                **previous_sales,
                "general_expenses": previous_expenses["general_expenses"],
                "expenses": previous_expenses["expenses"],
                "profit": previous_profit,
                "margin": pct(previous_profit, previous_sales["sales"]),
            }

            def change(current_value: Decimal, previous_value: Decimal) -> Decimal | None:
                current_value, previous_value = money(current_value), money(previous_value)
                if previous_value == ZERO:
                    return None if current_value != ZERO else ZERO
                return money((money(current_value - previous_value) / abs(previous_value)) * Decimal("100"))

            # Trend: only one row per bucket comes back from SQLite.
            return_totals = self._return_totals_subquery()
            net_total_expr, _cogs_expr, profit_expr = self._effective_sale_expressions(return_totals)
            bucket_expr = func.strftime("%Y-%m", Sale.sale_date) if monthly else func.strftime("%Y-%m-%d", Sale.sale_date)
            trend_sales = session.execute(
                select(
                    bucket_expr.label("bucket"),
                    func.coalesce(func.sum(net_total_expr), 0).label("sales"),
                    func.coalesce(func.sum(profit_expr), 0).label("profit"),
                    func.count(Sale.id).label("operations"),
                )
                .select_from(Sale)
                .outerjoin(return_totals, return_totals.c.sale_id == Sale.id)
                .where(*self._range_clause(Sale.sale_date, start, end))
                .group_by(bucket_expr)
            ).all()
            expense_bucket_expr = func.strftime("%Y-%m", Expense.expense_date) if monthly else func.strftime("%Y-%m-%d", Expense.expense_date)
            trend_expenses = session.execute(
                select(
                    expense_bucket_expr.label("bucket"),
                    func.coalesce(func.sum(Expense.amount), 0).label("expenses"),
                )
                .where(*self._range_clause(Expense.expense_date, start, end), Expense.direct_sale.is_(False))
                .group_by(expense_bucket_expr)
            ).all()
            trend_map: dict[str, dict[str, Decimal | int]] = defaultdict(
                lambda: {"sales": ZERO, "profit": ZERO, "expenses": ZERO, "operations": 0}
            )
            for row in trend_sales:
                key = str(row.bucket)
                trend_map[key]["sales"] = money(row.sales or 0)
                trend_map[key]["profit"] = money(row.profit or 0)
                trend_map[key]["operations"] = int(row.operations or 0)
            for row in trend_expenses:
                trend_map[str(row.bucket)]["expenses"] = money(row.expenses or 0)

            trend: list[dict] = []
            cursor = start.replace(hour=0, minute=0, second=0, microsecond=0)
            if monthly:
                cursor = cursor.replace(day=1)
                while cursor <= end:
                    key = cursor.strftime("%Y-%m")
                    row = trend_map.get(key, {"sales": ZERO, "profit": ZERO, "expenses": ZERO, "operations": 0})
                    trend.append({"key": key, "label": self._bucket_label(key, True), **row})
                    cursor = cursor.replace(year=cursor.year + (1 if cursor.month == 12 else 0), month=(1 if cursor.month == 12 else cursor.month + 1))
            else:
                while cursor <= end:
                    key = cursor.strftime("%Y-%m-%d")
                    row = trend_map.get(key, {"sales": ZERO, "profit": ZERO, "expenses": ZERO, "operations": 0})
                    trend.append({"key": key, "label": self._bucket_label(key, False), **row})
                    cursor += timedelta(days=1)

            # Payment methods and expense categories are both small grouped result sets.
            payment_rows = session.execute(
                select(
                    func.coalesce(Sale.payment_method, "Sin método").label("name"),
                    func.coalesce(func.sum(net_total_expr), 0).label("value"),
                )
                .select_from(Sale)
                .outerjoin(return_totals, return_totals.c.sale_id == Sale.id)
                .where(*self._range_clause(Sale.sale_date, start, end), net_total_expr > 0)
                .group_by(Sale.payment_method)
                .order_by(desc("value"))
            ).all()
            payment_methods = [{"name": str(r.name), "value": money(r.value or 0)} for r in payment_rows]

            expense_rows = session.execute(
                select(
                    func.coalesce(Expense.category, "Sin categoría").label("name"),
                    func.coalesce(func.sum(Expense.amount), 0).label("value"),
                )
                .where(*self._range_clause(Expense.expense_date, start, end))
                .group_by(Expense.category)
                .order_by(desc("value"))
            ).all()
            expense_categories = [{"name": str(r.name), "value": money(r.value or 0)} for r in expense_rows]

            top_products = self._top_products(session, start, end, limit=8)
            top_profitable_products = sorted(top_products, key=lambda row: row["profit"], reverse=True)[:8]

            inventory_value = money(
                session.scalar(select(func.coalesce(func.sum(InventoryLayer.remaining_quantity * InventoryLayer.unit_cost), 0))) or 0
            )
            invested = money(session.scalar(select(func.coalesce(func.sum(Purchase.total), 0))) or 0)
            products_count = int(session.scalar(select(func.count(Product.id)).where(Product.active.is_(True))) or 0)
            low_products = list(
                session.scalars(
                    select(Product)
                    .where(Product.active.is_(True), Product.stock_current > 0, Product.stock_current <= Product.stock_min)
                    .order_by(Product.stock_current.asc(), Product.name.asc(), Product.id.asc())
                    .limit(8)
                ).all()
            )
            out_products = list(
                session.scalars(
                    select(Product)
                    .where(Product.active.is_(True), Product.stock_current == 0)
                    .order_by(Product.name.asc(), Product.id.asc())
                    .limit(8)
                ).all()
            )
            low_count = int(session.scalar(select(func.count(Product.id)).where(
                Product.active.is_(True), Product.stock_current > 0, Product.stock_current <= Product.stock_min
            )) or 0)
            out_count = int(session.scalar(select(func.count(Product.id)).where(Product.active.is_(True), Product.stock_current == 0)) or 0)
            shipping_store, shipping_charged = self._shipping_totals(session, start, end)

            return {
                "period": period,
                "start": start,
                "end": end,
                "monthly_trend": monthly,
                "current": current,
                "previous": previous,
                "changes": {
                    "sales": change(current["sales"], previous["sales"]),
                    "profit": change(current["profit"], previous["profit"]),
                    "expenses": change(current["expenses"], previous["expenses"]),
                    "average_ticket": change(current["average_ticket"], previous["average_ticket"]),
                    "margin": money(current["margin"] - previous["margin"]),
                },
                "trend": trend,
                "payment_methods": payment_methods,
                "expense_categories": expense_categories,
                "top_products": top_products,
                "top_profitable_products": top_profitable_products,
                "low_products": [
                    {"name": p.name, "sku": p.sku, "stock": p.stock_current, "minimum": p.stock_min}
                    for p in low_products
                ],
                "out_products": [
                    {"name": p.name, "sku": p.sku, "stock": p.stock_current, "minimum": p.stock_min}
                    for p in out_products
                ],
                "inventory": {
                    "value": inventory_value,
                    "invested": invested,
                    "products_count": products_count,
                    "low_stock": low_count,
                    "out_of_stock": out_count,
                },
                "shipping": {"store_cost": shipping_store, "customer_charged": shipping_charged},
            }

    def _top_products(self, session, start: datetime, end: datetime, limit: int = 8) -> list[dict]:
        """Aggregate product performance in SQL without loading Sale ORM graphs."""
        return_totals = self._return_totals_subquery()
        return_item_cogs = self._return_item_cogs_subquery()
        net_qty = case((SaleItem.quantity > SaleItem.returned_quantity, SaleItem.quantity - SaleItem.returned_quantity), else_=0)
        net_line = case((SaleItem.quantity > 0, SaleItem.line_total * net_qty / SaleItem.quantity), else_=0)
        item_base = (
            select(
                SaleItem.id.label("item_id"),
                SaleItem.sale_id.label("sale_id"),
                SaleItem.product_id.label("product_id"),
                SaleItem.product_name_snapshot.label("name"),
                SaleItem.sku_snapshot.label("sku"),
                net_qty.label("net_qty"),
                net_line.label("net_line"),
                (SaleItem.cogs - func.coalesce(return_item_cogs.c.cogs_returned, 0)).label("net_cogs"),
                (Sale.discount - func.coalesce(return_totals.c.discount_refunded, 0)).label("remaining_discount"),
            )
            .select_from(SaleItem)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .outerjoin(return_item_cogs, return_item_cogs.c.sale_item_id == SaleItem.id)
            .outerjoin(return_totals, return_totals.c.sale_id == Sale.id)
            .where(*self._range_clause(Sale.sale_date, start, end))
            .subquery("dashboard_sale_items")
        )
        sale_line_totals = (
            select(
                item_base.c.sale_id,
                func.sum(item_base.c.net_line).label("net_lines_total"),
            )
            .group_by(item_base.c.sale_id)
            .subquery("dashboard_sale_line_totals")
        )
        allocated_discount = case(
            (sale_line_totals.c.net_lines_total > 0,
             item_base.c.remaining_discount * item_base.c.net_line / sale_line_totals.c.net_lines_total),
            else_=0,
        )
        product_revenue = item_base.c.net_line - case(
            (item_base.c.remaining_discount > 0, allocated_discount),
            else_=0,
        )
        rows = session.execute(
            select(
                item_base.c.product_id,
                item_base.c.name,
                item_base.c.sku,
                func.coalesce(func.sum(item_base.c.net_qty), 0).label("units"),
                func.coalesce(func.sum(product_revenue), 0).label("revenue"),
                func.coalesce(func.sum(item_base.c.net_cogs), 0).label("cogs"),
            )
            .select_from(item_base)
            .join(sale_line_totals, sale_line_totals.c.sale_id == item_base.c.sale_id)
            .group_by(item_base.c.product_id, item_base.c.name, item_base.c.sku)
            .order_by(desc("revenue"), asc(item_base.c.product_id))
            .limit(max(1, int(limit)))
        ).all()
        result = []
        for row in rows:
            revenue, cogs = money(row.revenue or 0), money(row.cogs or 0)
            profit = money(revenue - cogs)
            result.append({
                "name": str(row.name or "Producto"),
                "sku": str(row.sku or "—"),
                "units": int(row.units or 0),
                "revenue": revenue,
                "cogs": cogs,
                "profit": profit,
                "margin": pct(profit, revenue),
            })
        return result
