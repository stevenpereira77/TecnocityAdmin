"""Database indexes owned by the performance layer.

Keeping these definitions outside the migration routine makes future index changes
reviewable and prevents `init_db.py` from becoming a grab bag of tuning SQL.
"""
from __future__ import annotations

from sqlalchemy import text


PERFORMANCE_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_sales_date_status ON sales(sale_date, sale_status)",
    "CREATE INDEX IF NOT EXISTS idx_expenses_date_direct ON expenses(expense_date, direct_sale)",
    "CREATE INDEX IF NOT EXISTS idx_sale_returns_sale ON sale_returns(sale_id)",
    "CREATE INDEX IF NOT EXISTS idx_sale_return_items_sale_item ON sale_return_items(sale_item_id)",
    "CREATE INDEX IF NOT EXISTS idx_sale_items_sale_product ON sale_items(sale_id, product_id)",
    "CREATE INDEX IF NOT EXISTS idx_sale_items_product_sale ON sale_items(product_id, sale_id)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_layers_product_remaining ON inventory_layers(product_id, remaining_quantity)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_movements_product_date ON inventory_movements(product_id, occurred_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_logs_date_action ON audit_logs(occurred_at, action)",
)


def ensure_performance_indexes(conn) -> None:
    for statement in PERFORMANCE_INDEXES:
        conn.execute(text(statement))
