from __future__ import annotations

import base64

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy import inspect as sa_inspect

from app.core.exceptions import ValidationError
from app.database import create_database_engine, create_session_factory, initialize_database
from app.services import StoreService
from app.utils.product_images import validate_image_file

# Valid 1x1 transparent PNG; small but verifies binary persistence without Qt.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jKq0AAAAASUVORK5CYII="
)


def make_service():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    return engine, StoreService(create_session_factory(engine))


def test_product_image_data_round_trips_and_is_optional():
    engine, service = make_service()
    product = service.create_product(
        sku="IMG-001",
        name="Producto con foto",
        sale_price="120.00",
        image_data=TINY_PNG,
        image_thumbnail_data=TINY_PNG,
    )

    stored = service.get_product(product.id)
    assert stored is not None
    assert bytes(stored.image_data) == TINY_PNG
    assert bytes(stored.image_thumbnail_data) == TINY_PNG
    assert stored.image_path == ""

    # Lists load only thumbnails; the full-resolution column is deferred.
    listed = service.list_products()[0]
    assert "image_data" in sa_inspect(listed).unloaded
    assert bytes(listed.image_thumbnail_data) == TINY_PNG
    detailed = service.get_product(product.id)
    assert "image_data" not in sa_inspect(detailed).unloaded
    inventory_row = service.inventory_rows()[0]
    assert inventory_row["image_thumbnail_data"] == TINY_PNG
    assert "image_data" not in inventory_row

    # Ordinary edits must not erase a photo when no image change was requested.
    service.update_product(product.id, brand="Marca de prueba")
    assert bytes(service.get_product(product.id).image_data) == TINY_PNG

    # Explicit removal is represented by image_data=None and an empty legacy path.
    service.update_product(product.id, image_data=None, image_path="")
    assert service.get_product(product.id).image_data is None
    engine.dispose()


def test_invalid_product_image_bytes_are_rejected_before_persistence():
    _engine, service = make_service()
    with pytest.raises(ValidationError, match="imagen reconocida"):
        service.create_product(sku="IMG-BAD", name="Imagen inválida", sale_price="1", image_data=b"not-an-image")
    assert service.list_products() == []


def test_image_payload_size_is_bounded():
    _engine, service = make_service()
    too_large = b"\xff\xd8\xff" + (b"x" * (2 * 1024 * 1024))
    with pytest.raises(ValidationError, match="2 MB"):
        service.create_product(sku="IMG-LARGE", name="Imagen pesada", sale_price="1", image_data=too_large)
    assert service.list_products() == []


def test_existing_products_table_migrates_image_columns_without_losing_rows(tmp_path):
    db = tmp_path / "legacy_products.db"
    engine = create_engine(f"sqlite:///{db}", future=True)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE products (id INTEGER PRIMARY KEY, sku VARCHAR(60), name VARCHAR(160), "
            "sale_price NUMERIC(18,2), stock_min INTEGER, stock_current INTEGER, active BOOLEAN)"
        ))
        conn.execute(text("INSERT INTO products (id, sku, name, sale_price, stock_min, stock_current, active) VALUES (1, 'OLD-1', 'Producto anterior', 20, 0, 3, 1)"))
    initialize_database(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("products")}
    assert "image_path" in columns
    assert "image_data" in columns
    assert "image_thumbnail_data" in columns
    with engine.connect() as conn:
        row = conn.execute(text("SELECT sku, name, image_path, image_data, image_thumbnail_data FROM products WHERE id=1")).one()
    assert row.sku == "OLD-1"
    assert row.name == "Producto anterior"
    assert row.image_path == ""
    assert row.image_data is None
    assert row.image_thumbnail_data is None
    engine.dispose()


def test_image_bytes_are_included_in_normal_sqlite_database_snapshot(tmp_path):
    import sqlite3
    from app.backups import BackupManager
    from app.config import SettingsStore

    db_path = tmp_path / "tecnocity_admin.db"
    engine = create_database_engine(f"sqlite:///{db_path}")
    initialize_database(engine)
    service = StoreService(create_session_factory(engine))
    service.create_product(
        sku="BACKUP-IMG", name="Foto respaldada", sale_price="4.00",
        image_data=TINY_PNG, image_thumbnail_data=TINY_PNG,
    )
    engine.dispose()

    manager = BackupManager(
        database_path=db_path,
        backups_dir=tmp_path / "backups",
        credentials_path=tmp_path / "google" / "client_secret.json",
        token_path=tmp_path / "google" / "token.json",
        history_path=tmp_path / "backups" / "history.json",
        settings_store=SettingsStore(tmp_path / "settings.json"),
    )
    snapshot = manager.create_local_snapshot()
    with sqlite3.connect(snapshot) as conn:
        payload, thumbnail = conn.execute("SELECT image_data, image_thumbnail_data FROM products WHERE sku='BACKUP-IMG'").fetchone()
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert payload == TINY_PNG
    assert thumbnail == TINY_PNG


def test_source_image_validation_rejects_wrong_signature_and_empty_files(tmp_path, monkeypatch):
    valid = tmp_path / "foto.png"
    valid.write_bytes(TINY_PNG)
    assert validate_image_file(valid) == valid

    wrong = tmp_path / "foto.jpg"
    wrong.write_bytes(b"esto no es una imagen")
    with pytest.raises(ValueError, match="no coincide"):
        validate_image_file(wrong)

    empty = tmp_path / "vacia.png"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="vacía"):
        validate_image_file(empty)


def test_source_image_size_limit_is_enforced(tmp_path, monkeypatch):
    import app.utils.product_images as image_utils
    oversized = tmp_path / "large.jpg"
    oversized.write_bytes(b"\xff\xd8\xff" + b"x" * 32)
    monkeypatch.setattr(image_utils, "MAX_SOURCE_IMAGE_BYTES", 16)
    with pytest.raises(ValueError, match="20 MB"):
        validate_image_file(oversized)
