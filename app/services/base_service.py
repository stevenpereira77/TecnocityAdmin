"""Common infrastructure for all domain services."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Purchase, Sale


class BaseService:
    """Shared session/audit helpers for the application service layer.

    Domain services inherit from this class. They deliberately do not know
    about Qt or the GUI; they only coordinate database-backed business rules.
    """

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def _session(self):
        return self.session_factory()

    @staticmethod
    def _audit(
        session: Session,
        action: str,
        entity_type: str,
        entity_id: int | None,
        details: str,
    ) -> None:
        session.add(
            AuditLog(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                user_name="admin",
                details=details,
            )
        )

    @staticmethod
    def _next_document_number(session: Session, prefix: str) -> str:
        """Return the next human-readable purchase/sale number for today."""
        today = datetime.now().strftime("%Y%m%d")
        stamp = f"{prefix}-{today}"
        model = Purchase if prefix == "C" else Sale
        last = session.scalar(
            select(model.number)
            .where(model.number.like(f"{stamp}-%"))
            .order_by(model.number.desc())
            .limit(1)
        )
        seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{stamp}-{seq:04d}"
