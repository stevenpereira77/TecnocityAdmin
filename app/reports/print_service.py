from __future__ import annotations

from html import escape

from .formatting import format_period, format_value


def report_html(result, rows=None) -> str:
    """Render a report into printer-friendly HTML without importing Qt."""
    rows = tuple(result.rows if rows is None else rows)
    html_rows = []
    for row in rows:
        cells = "".join(
            f"<td>{escape(format_value(row.get(column.key), column.kind))}</td>"
            for column in result.columns
        )
        html_rows.append(f"<tr>{cells}</tr>")
    if not html_rows:
        html_rows.append(
            f'<tr><td colspan="{len(result.columns)}">Sin registros para el filtro seleccionado.</td></tr>'
        )
    header = "".join(f"<th>{escape(column.title)}</th>" for column in result.columns)
    summary = " · ".join(
        f"<b>{escape(str(label))}:</b> {escape(format_value(value, kind))}"
        for label, value, kind in result.summary
    )
    return f"""
    <html><head><style>
    body {{ font-family: Arial, sans-serif; color:#172033; }}
    h1 {{ font-size:18px; margin-bottom:4px; }}
    .meta {{ color:#64748b; font-size:9pt; }}
    .summary {{ background:#f8fafc; padding:7px; margin:10px 0; font-size:9pt; }}
    table {{ width:100%; border-collapse:collapse; font-size:7pt; }}
    th {{ background:#111827; color:white; padding:5px; text-align:left; }}
    td {{ border:1px solid #dbe3ec; padding:4px; vertical-align:top; }}
    tr:nth-child(even) td {{ background:#f8fafc; }}
    </style></head><body>
    <h1>{escape(result.definition.title)}</h1>
    <div class="meta">{escape(result.definition.description)}</div>
    <div class="meta">Período: {escape(format_period(result.start, result.end))} · Generado: {result.generated_at:%d/%m/%Y %H:%M:%S}</div>
    <div class="summary">{summary}</div>
    <table><thead><tr>{header}</tr></thead><tbody>{''.join(html_rows)}</tbody></table>
    </body></html>
    """


def print_report(parent, result, rows=None) -> bool:
    """Open the native Qt print dialog and print the selected report."""
    try:
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        from PySide6.QtGui import QTextDocument
        from PySide6.QtWidgets import QDialog
    except ModuleNotFoundError as exc:
        raise RuntimeError("La impresión requiere PySide6/Qt Print Support.") from exc

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    dialog = QPrintDialog(printer, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False

    document = QTextDocument()
    document.setHtml(report_html(result, rows))
    document.print_(printer)
    return True
