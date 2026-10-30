from __future__ import annotations

import csv
from pathlib import Path

from app.reports.formatting import format_period, format_value


def export_csv(result, path: str | Path, rows=None) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = tuple(result.rows if rows is None else rows)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Reporte", result.definition.title])
        writer.writerow(["Descripción", result.definition.description])
        writer.writerow(["Período", format_period(result.start, result.end)])
        writer.writerow(["Generado", result.generated_at.strftime("%d/%m/%Y %H:%M:%S")])
        writer.writerow([])
        writer.writerow([column.title for column in result.columns])
        for row in rows:
            writer.writerow([format_value(row.get(column.key), column.kind) for column in result.columns])
    return destination
