"""Session boundary helpers for future transactional operations."""
from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy.orm import Session, sessionmaker


@contextmanager
def session_scope(factory: sessionmaker) -> Iterator[Session]:
    """Commit on success; rollback on failure; always close the session."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
