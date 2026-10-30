"""Lightweight dashboard charts drawn with Qt's basic painting API.

This module intentionally uses only QtCore, QtGui and QtWidgets. It avoids the
optional Qt Charts add-on so the application does not depend on that module's
separate licensing terms and can keep its chart visuals without an extra chart
runtime dependency.
"""
from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.theme.palette import ThemePalette
from app.theme.themes import THEMES


def _number(value: object) -> float:
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError, OverflowError):
        return 0.0


def _compact(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000:
        return f"{value / 1_000_000:.1f} M"
    if absolute >= 1_000:
        return f"{value / 1_000:.1f} k"
    return f"{value:.0f}"


class _BaseDashboardChart(QWidget):
    """Shared background, title, empty-state and palette handling."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.palette = THEMES[0].palette
        self.rows: list[dict] = []
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def set_palette(self, palette: ThemePalette) -> None:
        self.palette = palette
        self.update()

    def set_rows(self, rows: Iterable[dict] | None) -> None:
        self.rows = list(rows or [])
        self.update()

    def row_count(self) -> int:
        return len(self.rows)

    def _begin(self) -> QPainter:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(self.palette.chart_axis), 1))
        painter.setBrush(QColor(self.palette.chart_bg))
        painter.drawRoundedRect(bounds, 10, 10)
        title_font = QFont(painter.font())
        title_font.setBold(True)
        title_font.setPointSize(max(9, title_font.pointSize()))
        painter.setFont(title_font)
        painter.setPen(QColor(self.palette.chart_text))
        painter.drawText(QRectF(16, 10, max(0, self.width() - 32), 24), Qt.AlignmentFlag.AlignVCenter, self.title)
        return painter

    def _draw_empty(self, painter: QPainter, message: str = "No hay datos para el período seleccionado") -> None:
        painter.setFont(QFont(painter.font().family(), 9))
        painter.setPen(QColor(self.palette.text_muted))
        painter.drawText(
            QRectF(20, 42, max(0, self.width() - 40), max(0, self.height() - 62)),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            message,
        )

    def _plot_background(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.palette.chart_plot_bg))
        painter.drawRoundedRect(rect, 7, 7)


class DashboardLineChart(_BaseDashboardChart):
    """Trend chart for sales, profit and expenses."""

    SERIES = (
        ("sales", "Ventas"),
        ("profit", "Ganancia"),
        ("expenses", "Gastos"),
    )

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override
        painter = self._begin()
        if not self.rows:
            self._draw_empty(painter)
            painter.end()
            return

        left, top, right, bottom = 58.0, 48.0, 16.0, 67.0
        plot = QRectF(left, top, max(1.0, self.width() - left - right), max(1.0, self.height() - top - bottom))
        self._plot_background(painter, plot)
        all_values = [_number(row.get(key, 0)) for row in self.rows for key, _ in self.SERIES]
        low = min(0.0, min(all_values, default=0.0))
        high = max(1.0, max(all_values, default=1.0))
        if high == low:
            high = low + 1.0
        span = high - low

        axis_font = QFont(painter.font())
        axis_font.setPointSize(8)
        painter.setFont(axis_font)
        for tick in range(5):
            ratio = tick / 4
            value = low + span * ratio
            y = plot.bottom() - ratio * plot.height()
            painter.setPen(QPen(QColor(self.palette.chart_grid), 1, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(self.palette.chart_text))
            painter.drawText(QRectF(2, y - 8, left - 10, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, _compact(value))

        count = len(self.rows)
        def point_x(index: int) -> float:
            return plot.center().x() if count == 1 else plot.left() + index * plot.width() / (count - 1)

        for series_index, (key, _label) in enumerate(self.SERIES):
            color = QColor(self.palette.chart_series[series_index % len(self.palette.chart_series)])
            pen = QPen(color, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            path = QPainterPath()
            points: list[QPointF] = []
            for index, row in enumerate(self.rows):
                value = _number(row.get(key, 0))
                y = plot.bottom() - ((value - low) / span) * plot.height()
                point = QPointF(point_x(index), y)
                points.append(point)
                if index == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.setPen(QPen(QColor(self.palette.chart_bg), 1))
            painter.setBrush(color)
            for point in points:
                painter.drawEllipse(point, 3.2, 3.2)

        label_font = QFont(axis_font)
        metrics = QFontMetrics(label_font)
        painter.setFont(label_font)
        max_labels = min(6, count)
        indices = sorted({round(i * (count - 1) / max(1, max_labels - 1)) for i in range(max_labels)})
        for index in indices:
            text = str(self.rows[index].get("label", ""))
            x = point_x(index)
            label_rect = QRectF(x - 40, plot.bottom() + 7, 80, 17)
            painter.setPen(QColor(self.palette.chart_text))
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, metrics.elidedText(text, Qt.TextElideMode.ElideRight, 78))

        legend_y = self.height() - 18
        legend_items = [(label, QColor(self.palette.chart_series[i % len(self.palette.chart_series)])) for i, (_key, label) in enumerate(self.SERIES)]
        total_width = sum(QFontMetrics(label_font).horizontalAdvance(label) + 32 for label, _ in legend_items) + 10 * (len(legend_items) - 1)
        cursor = max(12.0, (self.width() - total_width) / 2)
        painter.setFont(label_font)
        for label, color in legend_items:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QRectF(cursor, legend_y + 2, 8, 8))
            cursor += 13
            painter.setPen(QColor(self.palette.chart_text))
            painter.drawText(QPointF(cursor, legend_y + 10), label)
            cursor += QFontMetrics(label_font).horizontalAdvance(label) + 19
        painter.end()


class DashboardDonutChart(_BaseDashboardChart):
    """Payment-method share as a donut with a compact legend."""

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override
        painter = self._begin()
        valid = [(str(row.get("name", "Sin nombre")), max(0.0, _number(row.get("value", 0)))) for row in self.rows]
        valid = [(name, value) for name, value in valid if value > 0]
        total = sum(value for _, value in valid)
        if not valid or total <= 0:
            self._draw_empty(painter, "No hay ventas registradas para mostrar métodos de pago")
            painter.end()
            return

        chart_size = min(190.0, max(110.0, self.height() - 92.0), max(110.0, self.width() * 0.48))
        chart_rect = QRectF(18, (self.height() - chart_size) / 2 + 8, chart_size, chart_size)
        colors = [QColor(self.palette.chart_series[i % len(self.palette.chart_series)]) for i in range(len(valid))]
        start_angle = 90 * 16
        painter.setPen(QPen(QColor(self.palette.chart_bg), 1))
        for index, (_name, value) in enumerate(valid):
            span = round(value / total * 360 * 16)
            painter.setBrush(colors[index])
            painter.drawPie(chart_rect, start_angle, span)
            start_angle += span

        hole_rect = chart_rect.adjusted(chart_size * 0.27, chart_size * 0.27, -chart_size * 0.27, -chart_size * 0.27)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.palette.chart_bg))
        painter.drawEllipse(hole_rect)
        center_font = QFont(painter.font())
        center_font.setBold(True)
        center_font.setPointSize(11)
        painter.setFont(center_font)
        painter.setPen(QColor(self.palette.chart_text))
        painter.drawText(hole_rect, Qt.AlignmentFlag.AlignCenter, _compact(total))

        legend_left = chart_rect.right() + 22
        available = max(70.0, self.width() - legend_left - 12)
        row_height = min(32.0, max(22.0, (self.height() - 54.0) / min(7, len(valid))))
        legend_font = QFont(painter.font())
        legend_font.setBold(False)
        legend_font.setPointSize(8)
        painter.setFont(legend_font)
        for index, (name, value) in enumerate(valid[:7]):
            y = 38 + index * row_height
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colors[index])
            painter.drawRoundedRect(QRectF(legend_left, y + 4, 9, 9), 2, 2)
            painter.setPen(QColor(self.palette.chart_text))
            metrics = QFontMetrics(legend_font)
            label = metrics.elidedText(name, Qt.TextElideMode.ElideRight, int(available * 0.66))
            painter.drawText(QRectF(legend_left + 15, y, available * 0.66, 20), Qt.AlignmentFlag.AlignVCenter, label)
            painter.drawText(QRectF(legend_left + available * 0.68, y, available * 0.32, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{value / total * 100:.0f}%")
        painter.end()


class DashboardHorizontalBarChart(_BaseDashboardChart):
    """Compact horizontal bars for product revenue and expense categories."""

    def __init__(self, title: str, value_key: str, parent=None) -> None:
        super().__init__(title, parent)
        self.value_key = value_key

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override
        painter = self._begin()
        valid = [(str(row.get("name", "Sin nombre")), max(0.0, _number(row.get(self.value_key, 0)))) for row in self.rows]
        valid = [(name, value) for name, value in valid if value >= 0]
        limited = valid[:6]
        if not limited or max((value for _, value in limited), default=0) <= 0:
            self._draw_empty(painter)
            painter.end()
            return

        label_width = min(142.0, max(88.0, self.width() * 0.34))
        left = 16.0 + label_width
        right = 20.0
        bar_width = max(24.0, self.width() - left - right - 55.0)
        top = 48.0
        available_height = max(1.0, self.height() - top - 22.0)
        row_height = available_height / len(limited)
        maximum = max(value for _, value in limited) or 1.0
        font = QFont(painter.font())
        font.setPointSize(8)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        bar_color = QColor(self.palette.chart_series[0] if self.value_key == "revenue" else self.palette.chart_series[2])
        for index, (name, value) in enumerate(limited):
            y = top + index * row_height
            baseline = y + row_height * 0.5
            painter.setPen(QColor(self.palette.chart_text))
            label = metrics.elidedText(name, Qt.TextElideMode.ElideRight, int(label_width - 10))
            painter.drawText(QRectF(8, baseline - 11, label_width, 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            track = QRectF(left, baseline - 8, bar_width, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self.palette.chart_plot_bg))
            painter.drawRoundedRect(track, 6, 6)
            fill = QRectF(left, baseline - 8, max(2.0, bar_width * value / maximum), 16)
            painter.setBrush(bar_color)
            painter.drawRoundedRect(fill, 6, 6)
            painter.setPen(QColor(self.palette.chart_text))
            painter.drawText(QRectF(left + bar_width + 8, baseline - 11, max(34.0, self.width() - left - bar_width - 12), 22), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, _compact(value))
        painter.end()
