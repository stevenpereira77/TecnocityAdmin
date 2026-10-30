from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def create_database_engine(database_url: str) -> Engine:
    """Create a resilient SQLite engine tuned for the desktop workload.

    WAL improves read/write concurrency for a local desktop database. Foreign keys
    and a bounded busy timeout protect integrity when backups, scheduled tasks or
    multiple short-lived sessions touch the database close together.
    """
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, future=True, echo=False, connect_args=connect_args)

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA cache_size=-64000")
            if ":memory:" not in database_url and "mode=memory" not in database_url:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def create_session_factory(engine: Engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
