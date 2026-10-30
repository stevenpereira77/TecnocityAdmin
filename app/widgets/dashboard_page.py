from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import QDate, QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services import StoreService
from app.theme.palette import ThemePalette
from app.theme.themes import THEMES
from .dashboard_charts import DashboardDonutChart, DashboardHorizontalBarChart, DashboardLineChart
from .ui_helpers import fit_table, fmt_money





class DashboardPage(QWidget):
    """Executive dashboard with period filters, KPIs, trends and inventory alerts."""

    PERIODS = {
        "Hoy": "today",
        "Este mes": "month",
        "Últimos 7 días": "7d",
        "Últimos 30 días": "30d",
        "Últimos 90 días": "90d",
        "Este año": "year",
        "Mes anterior": "previous_month",
        "Todo el historial": "all",
    }

    def __init__(self, service: StoreService) -> None:
        super().__init__()
        self.service = service
        self._theme_palette = THEMES[0].palette
        self._build_ui()
        self.refresh()

    def on_theme_changed(self, theme_or_palette) -> None:
        """Refresh dashboard chart colors without reloading business data."""
        palette = getattr(theme_or_palette, "palette", theme_or_palette)
        if not isinstance(palette, ThemePalette):
            return
        self._theme_palette = palette
        for chart in (self.trend_chart, self.payment_chart, self.products_chart, self.expenses_chart):
            chart.set_palette(palette)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("pageContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 30)
        layout.setSpacing(16)
        scroll.setWidget(content)
        root.addWidget(scroll)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(3)
        title = QLabel("Dashboard ejecutivo")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Lectura rápida de ventas, rentabilidad, gastos, inventario y desempeño operativo.")
        subtitle.setObjectName("pageSubtitle")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap, 1)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.period_combo = QComboBox()
        self.period_combo.setObjectName("dashboardFilter")
        for label, key in self.PERIODS.items():
            self.period_combo.addItem(label, key)
        self.period_combo.addItem("Personalizado", "custom")
        self.period_combo.setCurrentText("Este mes")
        self._custom_initialized = False
        self.period_combo.currentIndexChanged.connect(self._period_changed)
        filters.addWidget(self.period_combo)

        self.start_edit = QDateEdit()
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setObjectName("dateFilter")
        self.start_edit.dateChanged.connect(self._on_custom_date_changed)
        self.start_edit.setVisible(False)
        filters.addWidget(self.start_edit)

        self.end_edit = QDateEdit()
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setObjectName("dateFilter")
        self.end_edit.dateChanged.connect(self._on_custom_date_changed)
        self.end_edit.setVisible(False)
        filters.addWidget(self.end_edit)

        refresh = QPushButton("Actualizar")
        refresh.setObjectName("secondaryButton")
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.clicked.connect(self.refresh)
        filters.addWidget(refresh)
        header.addLayout(filters)
        layout.addLayout(header)

        self.range_label = QLabel()
        self.range_label.setObjectName("dashboardRange")
        self.range_label.setProperty("state", "ok")
        layout.addWidget(self.range_label)

        self.cards: dict[str, dict[str, QLabel]] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        cards = [
            ("Ventas netas", "sales", "metricCardBlue"),
            ("Ganancia neta", "profit", "metricCardGreen"),
            ("Gastos", "expenses", "metricCardRed"),
            ("Margen neto", "margin", "metricCardPurple"),
            ("Ticket promedio", "average_ticket", "metricCardTeal"),
            ("Operaciones", "operations", "metricCard"),
            ("Inventario actual", "inventory", "metricCardAmber"),
            ("Productos activos", "products_count", "metricCardBlue"),
        ]
        for index, (label, key, style_name) in enumerate(cards):
            card = QGroupBox()
            card.setObjectName(style_name)
            box = QVBoxLayout(card)
            box.setContentsMargins(14, 12, 14, 13)
            label_widget = QLabel(label)
            label_widget.setObjectName("metricLabel")
            value_widget = QLabel("0")
            value_widget.setObjectName("metricValue")
            trend_widget = QLabel("Sin comparación")
            trend_widget.setObjectName("metricTrend")
            box.addWidget(label_widget)
            box.addWidget(value_widget)
            box.addWidget(trend_widget)
            self.cards[key] = {"value": value_widget, "trend": trend_widget}
            grid.addWidget(card, index // 4, index % 4)
        layout.addLayout(grid)

        charts_title = QLabel("Comportamiento del negocio")
        charts_title.setObjectName("sectionLabel")
        layout.addWidget(charts_title)

        charts_grid = QGridLayout()
        charts_grid.setHorizontalSpacing(14)
        charts_grid.setVerticalSpacing(14)

        self.trend_chart = DashboardLineChart("Ventas, ganancia y gastos")
        self.payment_chart = DashboardDonutChart("Distribución de ventas")
        self.products_chart = DashboardHorizontalBarChart("Productos más vendidos por valor", "revenue")
        self.expenses_chart = DashboardHorizontalBarChart("Gastos por categoría", "value")
        charts_grid.addWidget(self._chart_card("Tendencia", self.trend_chart), 0, 0)
        charts_grid.addWidget(self._chart_card("Métodos de pago", self.payment_chart), 0, 1)
        charts_grid.addWidget(self._chart_card("Productos", self.products_chart), 1, 0)
        charts_grid.addWidget(self._chart_card("Gastos", self.expenses_chart), 1, 1)
        layout.addLayout(charts_grid)

        # Bloque inferior: dos paneles simétricos.
        # El diseño anterior usaba una cuadrícula de 3 columnas con un panel
        # que ocupaba 2 columnas y otro que ocupaba 1; Qt terminaba asignando
        # casi todo el ancho al panel de alertas. La fila horizontal mantiene
        # ambos módulos con la misma jerarquía visual y evita el descuadre.
        lower_layout = QHBoxLayout()
        lower_layout.setSpacing(14)

        performance = QGroupBox("Productos más rentables")
        performance.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        performance_box = QVBoxLayout(performance)
        performance_box.setContentsMargins(10, 12, 10, 10)
        self.products_table = QTableWidget()
        self.products_table.setMinimumHeight(260)
        self.products_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.products_table.setColumnCount(5)
        self.products_table.setHorizontalHeaderLabels(["Producto", "Unid.", "Ventas", "Ganancia", "Margen"])
        fit_table(self.products_table, stretch_column=0)
        performance_box.addWidget(self.products_table)

        alerts = QGroupBox("Alertas y operación")
        alerts.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        alerts_box = QVBoxLayout(alerts)
        alerts_box.setContentsMargins(10, 12, 10, 10)
        self.stock_alert = QLabel()
        self.stock_alert.setObjectName("alertText")
        self.stock_alert.setWordWrap(True)
        alerts_box.addWidget(self.stock_alert)
        self.operation_summary = QLabel()
        self.operation_summary.setObjectName("mutedText")
        self.operation_summary.setWordWrap(True)
        alerts_box.addWidget(self.operation_summary)
        self.alert_table = QTableWidget()
        self.alert_table.setColumnCount(4)
        self.alert_table.setHorizontalHeaderLabels(["SKU", "Producto", "Stock", "Mínimo"])
        self.alert_table.setMinimumHeight(220)
        self.alert_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        fit_table(self.alert_table, stretch_column=1)
        alerts_box.addWidget(self.alert_table)

        lower_layout.addWidget(performance, 1)
        lower_layout.addWidget(alerts, 1)
        layout.addLayout(lower_layout)

        summary = QGroupBox("Lectura financiera")
        summary_box = QVBoxLayout(summary)
        self.history = QLabel()
        self.history.setObjectName("mutedText")
        self.history.setWordWrap(True)
        self.history.setTextInteractionFlags(Qt.TextSelectableByMouse)
        summary_box.addWidget(self.history)
        layout.addWidget(summary)
        layout.addStretch(1)

    @staticmethod
    def _chart_card(title: str, chart_widget: QWidget) -> QGroupBox:
        card = QGroupBox(title)
        card.setObjectName("chartCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(9, 12, 9, 9)
        box.addWidget(chart_widget)
        return card

    def _period_changed(self) -> None:
        custom = self.period_combo.currentData() == "custom"
        self.start_edit.setVisible(custom)
        self.end_edit.setVisible(custom)
        if custom and not self._custom_initialized:
            self._set_default_custom_dates()
            self._custom_initialized = True
        elif custom:
            self._sync_custom_date_limits()
        self.refresh()

    def _set_default_custom_dates(self) -> None:
        """Initialize the custom range atomically so dateChanged cannot refresh halfway."""
        today = QDate.currentDate()
        start = today.addDays(-29)
        end = today
        start_blocker = QSignalBlocker(self.start_edit)
        end_blocker = QSignalBlocker(self.end_edit)
        self.start_edit.setDate(start)
        self.end_edit.setDate(end)
        self.start_edit.setMaximumDate(end)
        self.end_edit.setMinimumDate(start)
        del start_blocker, end_blocker

    def _sync_custom_date_limits(self) -> None:
        """Keep the two date editors mutually constrained to a valid range."""
        start = self.start_edit.date()
        end = self.end_edit.date()
        if start > end:
            return
        start_blocker = QSignalBlocker(self.start_edit)
        end_blocker = QSignalBlocker(self.end_edit)
        self.start_edit.setMaximumDate(end)
        self.end_edit.setMinimumDate(start)
        del start_blocker, end_blocker

    def _on_custom_date_changed(self) -> None:
        if self.period_combo.currentData() != "custom":
            return
        start = self.start_edit.date()
        end = self.end_edit.date()
        if start > end:
            self.range_label.setProperty("state", "error")
            self.range_label.setText("Rango inválido: la fecha inicial no puede ser posterior a la fecha final.")
            self.range_label.style().unpolish(self.range_label)
            self.range_label.style().polish(self.range_label)
            return
        self._sync_custom_date_limits()
        self.refresh()

    def _selected_period(self) -> str:
        return str(self.period_combo.currentData() or "30d")

    def _report_kwargs(self) -> dict:
        period = self._selected_period()
        if period != "custom":
            return {"period": period}
        start_date = self.start_edit.date()
        end_date = self.end_edit.date()
        start = datetime(start_date.year(), start_date.month(), start_date.day())
        end = datetime(end_date.year(), end_date.month(), end_date.day(), 23, 59, 59, 999999)
        return {"period": "custom", "start": start, "end": end}

    @staticmethod
    def _date_text(value: datetime) -> str:
        return value.strftime("%d/%m/%Y")

    @staticmethod
    def _change_text(value: Decimal | None, *, inverse: bool = False) -> str:
        if value is None:
            return "• Sin base comparable"
        if value == 0:
            return "• Sin cambio vs. período anterior"
        arrow = "▲" if value > 0 else "▼"
        return f"{arrow} {abs(value):.2f}% vs. período anterior"

    def _set_card(self, key: str, value: str, change: Decimal | None, *, mode: str = "percent", inverse: bool = False) -> None:
        self.cards[key]["value"].setText(value)
        if mode == "points":
            if change == 0:
                text = "• Sin cambio vs. período anterior"
            else:
                arrow = "▲" if change > 0 else "▼"
                text = f"{arrow} {abs(change):.2f} pp vs. período anterior"
        else:
            text = self._change_text(change, inverse=inverse)
        self.cards[key]["trend"].setText(text)
        if change is None:
            direction = "neutral"
        elif change > 0:
            direction = "down" if inverse else "up"
        elif change < 0:
            direction = "up" if inverse else "down"
        else:
            direction = "neutral"
        self.cards[key]["trend"].setProperty("direction", direction)
        self.cards[key]["trend"].style().unpolish(self.cards[key]["trend"])
        self.cards[key]["trend"].style().polish(self.cards[key]["trend"])

    def _draw_trend(self, rows: list[dict]) -> None:
        self.trend_chart.set_rows(rows)

    def _draw_payment_chart(self, rows: list[dict]) -> None:
        self.payment_chart.set_rows(rows)

    @staticmethod
    def _draw_horizontal_bar(chart: DashboardHorizontalBarChart, rows: list[dict]) -> None:
        chart.set_rows(rows)

    def _fill_products_table(self, rows: list[dict]) -> None:
        self.products_table.setRowCount(0)
        for row in rows[:8]:
            r = self.products_table.rowCount()
            self.products_table.insertRow(r)
            values = [
                str(row["name"]),
                str(row["units"]),
                fmt_money(row["revenue"]),
                fmt_money(row["profit"]),
                f"{row['margin']}%",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.products_table.setItem(r, col, item)
        fit_table(self.products_table, stretch_column=0)

    def _fill_alert_table(self, low_products: list[dict], out_products: list[dict]) -> None:
        self.alert_table.setRowCount(0)
        rows = [("BAJO", row) for row in low_products] + [("AGOTADO", row) for row in out_products]
        for status, row in rows[:10]:
            r = self.alert_table.rowCount()
            self.alert_table.insertRow(r)
            values = [str(row["sku"]), str(row["name"]), str(row["stock"]), str(row["minimum"])]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.alert_table.setItem(r, col, item)
            self.alert_table.item(r, 0).setToolTip(status)
            if status == "AGOTADO":
                self.alert_table.item(r, 2).setText("AGOTADO")
        fit_table(self.alert_table, stretch_column=1)

    def refresh(self) -> None:
        try:
            data = self.service.dashboard_report(**self._report_kwargs())
        except ValueError as exc:
            self.range_label.setProperty("state", "error")
            self.range_label.setText(f"Rango inválido: {exc}")
            self.range_label.style().unpolish(self.range_label)
            self.range_label.style().polish(self.range_label)
            return

        current = data["current"]
        changes = data["changes"]
        inventory = data["inventory"]
        shipping = data["shipping"]

        self.range_label.setProperty("state", "ok")
        self.range_label.setText(
            f"Período analizado: <b>{self._date_text(data['start'])}</b> → <b>{self._date_text(data['end'])}</b> · "
            f"Comparación automática contra el período anterior"
        )
        self.range_label.style().unpolish(self.range_label)
        self.range_label.style().polish(self.range_label)

        self._set_card("sales", fmt_money(current["sales"]), changes["sales"])
        self._set_card("profit", fmt_money(current["profit"]), changes["profit"])
        self._set_card("expenses", fmt_money(current["expenses"]), changes["expenses"], inverse=True)
        self._set_card("margin", f"{current['margin']}%", changes["margin"], mode="points")
        self._set_card("average_ticket", fmt_money(current["average_ticket"]), changes["average_ticket"])
        self._set_card("operations", str(current["operations"]), Decimal("0"))
        self._set_card("inventory", fmt_money(inventory["value"]), Decimal("0"))
        self._set_card("products_count", str(inventory["products_count"]), Decimal("0"))

        self._draw_trend(data["trend"])
        self._draw_payment_chart(data["payment_methods"])
        self._draw_horizontal_bar(self.products_chart, data["top_products"])
        self._draw_horizontal_bar(self.expenses_chart, data["expense_categories"])
        self._fill_products_table(data["top_profitable_products"])
        self._fill_alert_table(data["low_products"], data["out_products"])

        low = inventory["low_stock"]
        out = inventory["out_of_stock"]
        if out or low:
            self.stock_alert.setText(f"⚠ {out} agotados · {low} con stock bajo")
        else:
            self.stock_alert.setText("✓ Inventario sin alertas de stock")

        self.operation_summary.setText(
            f"Inventario valorizado: <b>{fmt_money(inventory['value'])}</b><br>"
            f"Inversión histórica en compras: <b>{fmt_money(inventory['invested'])}</b><br>"
            f"Domicilios pagados por Tecnocity: <b>{fmt_money(shipping['store_cost'])}</b><br>"
            f"Domicilios cobrados al cliente: <b>{fmt_money(shipping['customer_charged'])}</b>"
        )

        gross = current["gross_profit"]
        self.history.setText(
            f"Ventas netas del período: <b>{fmt_money(current['sales'])}</b> · "
            f"Ganancia bruta: <b>{fmt_money(gross)}</b> · "
            f"Ganancia neta: <b>{fmt_money(current['profit'])}</b> · "
            f"Gastos totales: <b>{fmt_money(current['expenses'])}</b> · "
            f"Margen neto: <b>{current['margin']}%</b>.<br>"
            f"La métrica de ventas ya descuenta devoluciones/cancelaciones registradas. "
            f"Los gastos directos asociados a una venta permanecen integrados en su utilidad para evitar doble descuento."
        )
