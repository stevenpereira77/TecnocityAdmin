from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.models import Base
from app.database.indexes import ensure_performance_indexes

MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "products": [
        ("image_path", "VARCHAR(500) NOT NULL DEFAULT ''"),
        ("image_thumbnail_data", "BLOB NULL"),
        ("image_data", "BLOB NULL"),
    ],
    "sales": [
        ("shipping_charge", "NUMERIC(18,2) NOT NULL DEFAULT 0"),
        ("shipping_payer", "VARCHAR(30) NOT NULL DEFAULT 'TIENDA'"),
        ("shipping_refunded", "NUMERIC(18,2) NOT NULL DEFAULT 0"),
        ("sale_status", "VARCHAR(30) NOT NULL DEFAULT 'CONFIRMADA'"),
        ("delivery_status", "VARCHAR(30) NOT NULL DEFAULT 'PENDIENTE'"),
        ("customer_name", "VARCHAR(160) NOT NULL DEFAULT ''"),
        ("customer_phone", "VARCHAR(60) NOT NULL DEFAULT ''"),
        ("customer_address", "VARCHAR(300) NOT NULL DEFAULT ''"),
        ("cancelled_at", "DATETIME NULL"),
        ("cancellation_reason", "VARCHAR(250) NOT NULL DEFAULT ''"),
        ("returned_at", "DATETIME NULL"),
        ("original_subtotal", "NUMERIC(18,2) NOT NULL DEFAULT 0"),
        ("original_total", "NUMERIC(18,2) NOT NULL DEFAULT 0"),
        ("original_cogs", "NUMERIC(18,2) NOT NULL DEFAULT 0"),
        ("original_gross_profit", "NUMERIC(18,2) NOT NULL DEFAULT 0"),
        ("original_net_profit", "NUMERIC(18,2) NOT NULL DEFAULT 0"),
    ],
    "sale_items": [
        ("returned_quantity", "INTEGER NOT NULL DEFAULT 0"),
    ],
}


def initialize_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        inspector = inspect(conn)
        for table_name, columns in MIGRATIONS.items():
            existing = {col["name"] for col in inspector.get_columns(table_name)}
            for column_name, definition in columns:
                if column_name not in existing:
                    conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {definition}'))
            inspector = inspect(conn)

        conn.execute(text("""
            UPDATE sales
            SET original_subtotal = subtotal,
                original_total = total,
                original_cogs = cogs,
                original_gross_profit = gross_profit,
                original_net_profit = net_profit
            WHERE original_total = 0 AND total <> 0
        """))
        conn.execute(text("UPDATE sales SET shipping_payer='TIENDA' WHERE shipping_payer IS NULL OR shipping_payer=''"))
        conn.execute(text("UPDATE sales SET sale_status='CONFIRMADA' WHERE sale_status IS NULL OR sale_status=''"))
        conn.execute(text("UPDATE sales SET delivery_status='PENDIENTE' WHERE delivery_status IS NULL OR delivery_status=''"))

        ensure_performance_indexes(conn)
        conn.execute(text("PRAGMA optimize"))
