from sqlalchemy import create_engine, text, inspect

from app.database import initialize_database


def test_v11_schema_is_migrated_without_dropping_existing_sale(tmp_path):
    db = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db}", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY, sku VARCHAR(60), name VARCHAR(160), sale_price NUMERIC(18,2), stock_min INTEGER, stock_current INTEGER, active BOOLEAN)"))
        conn.execute(text("CREATE TABLE purchases (id INTEGER PRIMARY KEY, number VARCHAR(60), purchase_date DATETIME, supplier VARCHAR(160), shipping_cost NUMERIC(18,2), other_cost NUMERIC(18,2), subtotal NUMERIC(18,2), total NUMERIC(18,2), notes TEXT)"))
        conn.execute(text("CREATE TABLE sale_items (id INTEGER PRIMARY KEY, sale_id INTEGER, product_id INTEGER, sku_snapshot VARCHAR(60), product_name_snapshot VARCHAR(160), quantity INTEGER, unit_sale_price NUMERIC(18,2), discount NUMERIC(18,2), line_total NUMERIC(18,2), cogs NUMERIC(18,2))"))
        conn.execute(text("CREATE TABLE sales (id INTEGER PRIMARY KEY, number VARCHAR(60), sale_date DATETIME, discount NUMERIC(18,2), shipping_cost NUMERIC(18,2), other_cost NUMERIC(18,2), commission NUMERIC(18,2), payment_method VARCHAR(60), subtotal NUMERIC(18,2), total NUMERIC(18,2), cogs NUMERIC(18,2), gross_profit NUMERIC(18,2), net_profit NUMERIC(18,2), notes TEXT)"))
        conn.execute(text("CREATE TABLE purchase_items (id INTEGER PRIMARY KEY, purchase_id INTEGER, product_id INTEGER, quantity INTEGER, unit_cost NUMERIC(18,2), line_total NUMERIC(18,2))"))
        conn.execute(text("CREATE TABLE inventory_layers (id INTEGER PRIMARY KEY, product_id INTEGER, purchase_item_id INTEGER, received_at DATETIME, original_quantity INTEGER, remaining_quantity INTEGER, unit_cost NUMERIC(18,2))"))
        conn.execute(text("CREATE TABLE inventory_movements (id INTEGER PRIMARY KEY, product_id INTEGER, movement_type VARCHAR(40), quantity INTEGER, occurred_at DATETIME, document_type VARCHAR(40), document_id INTEGER, reason VARCHAR(200), user_name VARCHAR(120), notes TEXT)"))
        conn.execute(text("CREATE TABLE expenses (id INTEGER PRIMARY KEY, expense_date DATETIME, category VARCHAR(80), description VARCHAR(200), amount NUMERIC(18,2), sale_id INTEGER, direct_sale BOOLEAN, notes TEXT)"))
        conn.execute(text("INSERT INTO sales (id, number, subtotal, total, cogs, gross_profit, net_profit, shipping_cost) VALUES (1, 'V-20260927-0001', 100, 100, 40, 60, 50, 10)"))

    initialize_database(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("sales")}
    assert "shipping_charge" in columns
    assert "shipping_payer" in columns
    assert "sale_status" in columns
    with engine.connect() as conn:
        row = conn.execute(text("SELECT number, original_total, sale_status FROM sales WHERE id=1")).one()
        assert row.number == "V-20260927-0001"
        assert row.original_total == 100
        assert row.sale_status == "CONFIRMADA"
        assert "audit_logs" in inspect(conn).get_table_names()
        assert "sale_returns" in inspect(conn).get_table_names()
        product_columns = {col["name"] for col in inspect(conn).get_columns("products")}
        assert "image_path" in product_columns
        assert "image_data" in product_columns
        assert "image_thumbnail_data" in product_columns
