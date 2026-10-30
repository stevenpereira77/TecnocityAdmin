from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from app.database import create_database_engine, create_session_factory, initialize_database
from app.services import ProductFilter, ReportingService, StoreService


def measure(label, func):
    started = time.perf_counter()
    result = func()
    elapsed = time.perf_counter() - started
    print(f"{label:<28} {elapsed:>8.3f} s")
    return result, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Tecnocity Admin en una base local.")
    parser.add_argument("--database", default="data/tecnocity_admin.db", help="Ruta a la base SQLite.")
    args = parser.parse_args()
    db = Path(args.database).resolve()
    if not db.exists():
        print(f"No existe la base: {db}")
        return 2

    engine = create_database_engine(f"sqlite:///{db}")
    initialize_database(engine)
    factory = create_session_factory(engine)
    service = StoreService(factory)
    reporting = ReportingService(factory)

    print(f"Base: {db}")
    print("Benchmark de lectura")
    print("-" * 42)
    measure("Dashboard mes", lambda: reporting.dashboard_report(period="month", now=datetime(2026, 9, 30, 12, 0)))
    measure("Dashboard 30 días", lambda: reporting.dashboard_report(period="30d", now=datetime(2026, 9, 30, 12, 0)))
    measure("Dashboard histórico", lambda: reporting.dashboard_report(period="all", now=datetime(2026, 9, 30, 12, 0)))
    measure("Productos página 1", lambda: service.list_products_page(ProductFilter(sort_by="id", sort_direction="desc"), page=1, page_size=100))
    measure("Inventario página 1", lambda: service.inventory_rows(limit=100, offset=0))
    measure("Movimientos recientes", lambda: service.movements(limit=100))
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
