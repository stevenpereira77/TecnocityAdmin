from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from html import escape

from .definitions import ReportColumn

MONEY_FORMAT = "$#,##0.00"
PERCENT_FORMAT = "0.00%"


def format_value(value, kind: str) -> str:
    if value is None:
        return ""
    if kind == "money":
        return f"${Decimal(str(value)):,.2f}"
    if kind == "percent":
        return f"{Decimal(str(value)):,.2f}%"
    if kind == "integer":
        return f"{int(value):,}".replace(",", ".")
    if kind == "datetime":
        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y %H:%M")
        return str(value)
    if kind == "date":
        if isinstance(value, (datetime, date)):
            return value.strftime("%d/%m/%Y")
    return str(value)


def format_period(start: datetime | None, end: datetime | None) -> str:
    if start is None or end is None:
        return "Inventario actual"
    return f"{start:%d/%m/%Y} → {end:%d/%m/%Y}"


def html_table(result, rows) -> str:
    headers = "".join(f"<th>{escape(column.title)}</th>" for column in result.columns)
    body = []
    for row in rows:
        cells = "".join(
            f"<td>{escape(format_value(row.get(column.key), column.kind))}</td>"
            for column in result.columns
        )
        body.append(f"<tr>{cells}</tr>")
    if not body:
        body.append(f'<tr><td colspan="{len(result.columns)}" class="empty">Sin registros para el filtro seleccionado.</td></tr>')
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(body)}</tbody></table>"
