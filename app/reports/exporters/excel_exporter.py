from __future__ import annotations

from pathlib import Path
from re import sub

from app.reports.formatting import format_period


def export_excel(result, path: str | Path, rows=None) -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.worksheet.table import Table, TableStyleInfo
    except ModuleNotFoundError as exc:
        raise RuntimeError("La exportación Excel requiere openpyxl. Ejecuta pip install -r requirements.txt") from exc

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = tuple(result.rows if rows is None else rows)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Reporte"
    sheet.sheet_view.showGridLines = False

    dark_fill = PatternFill("solid", fgColor="111827")
    header_fill = PatternFill("solid", fgColor="E5E7EB")
    summary_fill = PatternFill("solid", fgColor="F8FAFC")
    white_font = Font(color="FFFFFF", bold=True, size=15)
    header_font = Font(color="334155", bold=True)
    title_font = Font(color="111827", bold=True, size=14)
    border = Border(bottom=Side(style="thin", color="D1D5DB"))

    end_col = max(1, len(result.columns))
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=end_col)
    sheet.cell(1, 1, result.definition.title)
    sheet.cell(1, 1).fill = dark_fill
    sheet.cell(1, 1).font = white_font
    sheet.cell(1, 1).alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 28

    sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=end_col)
    sheet.cell(2, 1, result.definition.description)
    sheet.cell(2, 1).font = Font(color="64748B", italic=True)

    sheet.cell(3, 1, "Período")
    sheet.cell(3, 2, format_period(result.start, result.end))
    sheet.cell(4, 1, "Generado")
    sheet.cell(4, 2, result.generated_at.strftime("%d/%m/%Y %H:%M:%S"))
    for row in (3, 4):
        sheet.cell(row, 1).font = Font(bold=True, color="475569")
        sheet.cell(row, 2).font = Font(color="334155")

    summary_start = 5
    for index, (label, value, kind) in enumerate(result.summary, start=summary_start):
        sheet.cell(index, 1, label)
        sheet.cell(index, 2, value)
        sheet.cell(index, 1).fill = summary_fill
        sheet.cell(index, 2).fill = summary_fill
        sheet.cell(index, 1).font = Font(bold=True, color="475569")
        sheet.cell(index, 2).font = title_font
        if kind == "money":
            sheet.cell(index, 2).number_format = '$#,##0.00'
        elif kind == "percent":
            sheet.cell(index, 2).number_format = '0.00"%"'

    header_row = 5 + max(len(result.summary), 1) + 1
    sheet.freeze_panes = f"A{header_row + 1}"
    for col_idx, column in enumerate(result.columns, start=1):
        cell = sheet.cell(header_row, col_idx, column.title)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for row_idx, row in enumerate(rows, start=header_row + 1):
        for col_idx, column in enumerate(result.columns, start=1):
            value = row.get(column.key)
            cell = sheet.cell(row_idx, col_idx, value)
            if column.kind == "money":
                cell.number_format = '$#,##0.00'
                cell.alignment = Alignment(horizontal="right")
            elif column.kind == "percent":
                cell.number_format = '0.00"%"'
                cell.alignment = Alignment(horizontal="right")
            elif column.kind == "integer":
                cell.number_format = '#,##0'
                cell.alignment = Alignment(horizontal="right")
            elif column.kind == "datetime":
                cell.number_format = 'dd/mm/yyyy hh:mm'
            elif column.kind == "date":
                cell.number_format = 'dd/mm/yyyy'
            else:
                cell.alignment = Alignment(vertical="top", wrap_text=True)

    data_start = header_row
    data_end = header_row + len(rows)
    if rows:
        table_ref = f"A{data_start}:{get_column_letter(len(result.columns))}{data_end}"
        name = sub(r"[^A-Za-z0-9_]", "", result.definition.key.title()) or "Reporte"
        table = Table(displayName=f"Tbl{name}", ref=table_ref)
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
        sheet.add_table(table)
        sheet.auto_filter.ref = table_ref

    widths = {}
    for index, column in enumerate(result.columns, start=1):
        width = max(len(column.title) + 2, 12)
        for row in rows[:150]:
            width = max(width, min(len(str(row.get(column.key, ""))) + 2, 42))
        widths[index] = min(width, 42)
    for index, width in widths.items():
        sheet.column_dimensions[get_column_letter(index)].width = width

    workbook.save(destination)
    return destination
