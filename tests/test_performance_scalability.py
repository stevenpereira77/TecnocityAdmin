from __future__ import annotations

import importlib.util
import time
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from app.database import create_database_engine, create_session_factory, initialize_database
from app.services import ProductFilter, ReportingService, StoreService


ROOT = Path(__file__).resolve().parents[1]


def test_main_window_uses_lazy_page_hosts_and_targeted_refresh():
    source = (ROOT / "app" / "views" / "main_window.py").read_text(encoding="utf-8")
    assert "LazyPageHost" in source
    assert "QTimer.singleShot(0" in source
    assert "def refresh_current_page" in source
    assert "if page.is_loaded" in source


def test_reporting_service_does_not_materialize_sales_history_for_dashboard():
    source = (ROOT / "app" / "services" / "reporting_service.py").read_text(encoding="utf-8")
    body = source[source.index("    def dashboard_report("):source.index("    def _top_products(")]
    assert "select(Sale).options(" not in body
    assert ".all())" not in body.split("def _top_products", 1)[0]
    assert "_sales_summary(session" in body
    assert "_top_products(session" in body


def test_sqlite_indexes_for_critical_read_paths_are_created(tmp_path):
    db = tmp_path / "tec.db"
    engine = create_database_engine(f"sqlite:///{db}")
    initialize_database(engine)
    names = {idx["name"] for idx in inspect(engine).get_indexes("sales")}
    assert "idx_sales_date_status" in names
    names = {idx["name"] for idx in inspect(engine).get_indexes("expenses")}
    assert "idx_expenses_date_direct" in names
    engine.dispose()


def test_product_pagination_bounds_large_result_sets():
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    service = StoreService(create_session_factory(engine))
    for idx in range(350):
        service.create_product(sku=f"P-{idx:04d}", name=f"Producto {idx}", sale_price="10.00")
    rows, total = service.list_products_page(ProductFilter(sort_by="id", sort_direction="desc"), page=2, page_size=100)
    assert len(rows) == 100
    assert total == 350
    assert rows[0].id == 250
    engine.dispose()


def test_dashboard_aggregate_path_is_fast_on_a_large_synthetic_db():
    """Opt-in stress test: set TECNOCITY_STRESS_DB to a local stress DB to run it."""
    import os
    db = os.getenv("TECNOCITY_STRESS_DB")
    if not db or not Path(db).exists():
        pytest.skip("TECNOCITY_STRESS_DB no configurado.")
    engine = create_database_engine(f"sqlite:///{Path(db)}")
    initialize_database(engine)
    service = ReportingService(create_session_factory(engine))
    t0 = time.perf_counter()
    result = service.dashboard_report(period="month", now=datetime(2026, 9, 30, 12, 0))
    elapsed = time.perf_counter() - t0
    assert result["current"]["operations"] >= 0
    assert elapsed < 5.0
    engine.dispose()
