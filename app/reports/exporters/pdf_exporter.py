from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from app.reports.formatting import format_period, format_value


def export_pdf(result, path: str | Path, rows=None) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ModuleNotFoundError as exc:
        raise RuntimeError("La exportación PDF requiere reportlab. Ejecuta pip install -r requirements.txt") from exc

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = tuple(result.rows if rows is None else rows)

    landscape_mode = len(result.columns) >= 8
    page_size = landscape(A4) if landscape_mode else A4
    document = SimpleDocTemplate(
        str(destination),
        pagesize=page_size,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=13 * mm,
        bottomMargin=13 * mm,
        title=result.definition.title,
        author="Tecnocity Admin",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=colors.HexColor("#111827"), alignment=TA_LEFT, spaceAfter=4)
    subtitle_style = ParagraphStyle("ReportSubtitle", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor("#64748B"), spaceAfter=3)
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontName="Helvetica", fontSize=6.8 if landscape_mode else 8.0, leading=8.2 if landscape_mode else 9.5, textColor=colors.HexColor("#172033"))
    head_style = ParagraphStyle("Head", parent=cell_style, fontName="Helvetica-Bold", textColor=colors.white, fontSize=max(6.4, cell_style.fontSize), leading=cell_style.leading)
    meta_style = ParagraphStyle("Meta", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#475569"), spaceAfter=2)
    summary_style = ParagraphStyle("Summary", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#172033"), leading=11)

    story = [
        Paragraph(escape(result.definition.title), title_style),
        Paragraph(escape(result.definition.description), subtitle_style),
        Paragraph(f"<b>Período:</b> {escape(format_period(result.start, result.end))}", meta_style),
        Paragraph(f"<b>Generado:</b> {result.generated_at:%d/%m/%Y %H:%M:%S}", meta_style),
        Spacer(1, 5 * mm),
    ]
    if result.summary:
        summary_data = [[Paragraph(escape(label), summary_style), Paragraph(escape(format_value(value, kind)), summary_style)] for label, value, kind in result.summary]
        summary_table = Table(summary_data, colWidths=[42 * mm, 42 * mm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E0E8")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([summary_table, Spacer(1, 5 * mm)])

    widths = [max(16 * mm, (page_size[0] - 24 * mm) / len(result.columns))] * len(result.columns)
    header = [Paragraph(escape(column.title), head_style) for column in result.columns]
    data = [header]
    for row in rows:
        data.append([Paragraph(escape(format_value(row.get(column.key), column.kind)), cell_style) for column in result.columns])
    if not rows:
        data.append([Paragraph("Sin registros para el filtro seleccionado.", cell_style)] + [""] * (len(result.columns) - 1))

    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DCE2EA")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for index, column in enumerate(result.columns):
        if column.kind in {"money", "integer", "percent"}:
            table_style.append(("ALIGN", (index, 1), (index, -1), "RIGHT"))
    for row_index in range(1, len(data)):
        if row_index % 2 == 0:
            table_style.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#F8FAFC")))
    table.setStyle(TableStyle(table_style))
    story.append(table)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(12 * mm, 7 * mm, "Tecnocity Admin · Reporte generado automáticamente")
        canvas.drawRightString(page_size[0] - 12 * mm, 7 * mm, f"Página {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    if destination.stat().st_size < 100:
        raise RuntimeError("El PDF generado parece inválido o vacío.")
    return destination
