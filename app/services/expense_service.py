"""Expense business operations."""
from __future__ import annotations

from datetime import datetime

from app.calculations.financial import money
from app.core.exceptions import ValidationError
from app.models import Expense, Sale
from app.services.base_service import BaseService


class ExpenseService(BaseService):
    """Registers general expenses and costs linked directly to a sale."""

    def register_expense(
        self,
        *,
        category: str,
        description: str,
        amount,
        direct_sale: bool = False,
        sale_id: int | None = None,
        notes: str = "",
        expense_date: datetime | None = None,
    ) -> Expense:
        amount = money(amount)
        if amount <= 0:
            raise ValidationError("El valor del gasto debe ser mayor que cero.")
        if not category.strip() or not description.strip():
            raise ValidationError("Categoría y descripción son obligatorias.")

        with self._session() as session:
            sale = session.get(Sale, int(sale_id)) if sale_id is not None else None
            if direct_sale and sale is None:
                raise ValidationError("Un gasto directo debe estar relacionado con una venta.")

            expense = Expense(
                expense_date=expense_date or datetime.now(),
                category=category.strip(),
                description=description.strip(),
                amount=amount,
                direct_sale=bool(direct_sale),
                sale_id=sale_id,
                notes=notes.strip(),
            )
            session.add(expense)
            session.flush()
            if sale is not None and direct_sale:
                sale.net_profit = money(sale.net_profit - amount)

            self._audit(
                session,
                "CREAR",
                "GASTO",
                expense.id,
                f"valor={amount}; directo={direct_sale}; venta={sale_id or '-'}",
            )
            session.commit()
            session.refresh(expense)
            return expense
