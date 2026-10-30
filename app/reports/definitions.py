from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ColumnKind = Literal["text", "date", "datetime", "money", "integer", "percent"]


@dataclass(frozen=True, slots=True)
class ReportColumn:
    key: str
    title: str
    kind: ColumnKind = "text"


@dataclass(frozen=True, slots=True)
class ReportDefinition:
    key: str
    title: str
    description: str
    columns: tuple[ReportColumn, ...]
    date_filtered: bool = True
    search_placeholder: str = "Buscar en el reporte..."


REPORT_DEFINITIONS: tuple[ReportDefinition, ...] = (
    ReportDefinition(
        key="sales",
        title="Ventas",
        description="Detalle de ventas, devoluciones, ingresos netos y rentabilidad por operación.",
        columns=(
            ReportColumn("date", "Fecha", "datetime"),
            ReportColumn("number", "Venta", "text"),
            ReportColumn("status", "Estado", "text"),
            ReportColumn("customer", "Cliente", "text"),
            ReportColumn("payment_method", "Pago", "text"),
            ReportColumn("items", "Ítems", "integer"),
            ReportColumn("subtotal", "Subtotal", "money"),
            ReportColumn("discount", "Descuento", "money"),
            ReportColumn("shipping", "Domicilio", "money"),
            ReportColumn("original_total", "Total original", "money"),
            ReportColumn("refunded", "Reembolsado", "money"),
            ReportColumn("net_total", "Venta neta", "money"),
            ReportColumn("cogs", "COGS", "money"),
            ReportColumn("gross_profit", "Ganancia bruta", "money"),
            ReportColumn("net_profit", "Ganancia neta", "money"),
        ),
        search_placeholder="Buscar venta, cliente, estado, pago...",
    ),
    ReportDefinition(
        key="purchases",
        title="Compras",
        description="Compras realizadas, costos asociados y valor total incorporado al inventario.",
        columns=(
            ReportColumn("date", "Fecha", "datetime"),
            ReportColumn("number", "Compra", "text"),
            ReportColumn("supplier", "Proveedor", "text"),
            ReportColumn("items", "Ítems", "integer"),
            ReportColumn("subtotal", "Subtotal", "money"),
            ReportColumn("shipping", "Transporte", "money"),
            ReportColumn("other_cost", "Otros costos", "money"),
            ReportColumn("total", "Total compra", "money"),
        ),
        search_placeholder="Buscar compra, proveedor...",
    ),
    ReportDefinition(
        key="inventory",
        title="Inventario",
        description="Existencia actual, valorización FIFO, stock mínimo y precio de venta.",
        columns=(
            ReportColumn("sku", "SKU", "text"),
            ReportColumn("name", "Producto", "text"),
            ReportColumn("category", "Categoría", "text"),
            ReportColumn("brand", "Marca", "text"),
            ReportColumn("stock", "Stock", "integer"),
            ReportColumn("minimum", "Mínimo", "integer"),
            ReportColumn("unit_cost", "Costo unit. FIFO (prom.)", "money"),
            ReportColumn("inventory_value", "Valor inventario", "money"),
            ReportColumn("sale_price", "Precio venta", "money"),
            ReportColumn("margin", "Margen %", "percent"),
            ReportColumn("status", "Estado", "text"),
        ),
        date_filtered=False,
        search_placeholder="Buscar SKU, producto, categoría, marca...",
    ),
    ReportDefinition(
        key="profitability",
        title="Utilidades",
        description="Evolución de ventas netas, COGS, gastos generales y utilidad neta.",
        columns=(
            ReportColumn("period", "Período", "text"),
            ReportColumn("sales", "Ventas netas", "money"),
            ReportColumn("cogs", "COGS", "money"),
            ReportColumn("gross_profit", "Ganancia bruta", "money"),
            ReportColumn("general_expenses", "Gastos generales", "money"),
            ReportColumn("net_profit", "Ganancia neta", "money"),
            ReportColumn("margin", "Margen neto", "percent"),
            ReportColumn("operations", "Operaciones", "integer"),
        ),
        search_placeholder="Buscar período...",
    ),
    ReportDefinition(
        key="expenses",
        title="Gastos",
        description="Detalle de gastos generales y gastos asociados directamente a ventas.",
        columns=(
            ReportColumn("date", "Fecha", "datetime"),
            ReportColumn("category", "Categoría", "text"),
            ReportColumn("description", "Descripción", "text"),
            ReportColumn("type", "Tipo", "text"),
            ReportColumn("sale_number", "Venta asociada", "text"),
            ReportColumn("amount", "Importe", "money"),
            ReportColumn("notes", "Notas", "text"),
        ),
        search_placeholder="Buscar categoría, descripción, venta...",
    ),
    ReportDefinition(
        key="returns",
        title="Devoluciones",
        description="Devoluciones procesadas, importes reembolsados y costo de inventario restituido.",
        columns=(
            ReportColumn("date", "Fecha", "datetime"),
            ReportColumn("sale_number", "Venta", "text"),
            ReportColumn("customer", "Cliente", "text"),
            ReportColumn("reason", "Motivo", "text"),
            ReportColumn("products_refunded", "Productos", "money"),
            ReportColumn("discount_refunded", "Descuento", "money"),
            ReportColumn("shipping_refunded", "Domicilio", "money"),
            ReportColumn("total_refunded", "Total reembolsado", "money"),
            ReportColumn("cogs_returned", "COGS devuelto", "money"),
            ReportColumn("profit_impact", "Impacto utilidad", "money"),
            ReportColumn("items", "Ítems", "integer"),
        ),
        search_placeholder="Buscar venta, cliente, motivo...",
    ),
    ReportDefinition(
        key="cancellations",
        title="Cancelaciones",
        description="Ventas canceladas con su trazabilidad y valores económicos originales.",
        columns=(
            ReportColumn("cancelled_at", "Cancelada", "datetime"),
            ReportColumn("sale_date", "Fecha venta", "datetime"),
            ReportColumn("number", "Venta", "text"),
            ReportColumn("customer", "Cliente", "text"),
            ReportColumn("reason", "Motivo", "text"),
            ReportColumn("original_total", "Total original", "money"),
            ReportColumn("original_cogs", "COGS original", "money"),
            ReportColumn("original_net_profit", "Utilidad original", "money"),
        ),
        search_placeholder="Buscar venta, cliente, motivo...",
    ),
    ReportDefinition(
        key="audit",
        title="Auditoría",
        description="Registro de operaciones sensibles realizadas dentro del sistema.",
        columns=(
            ReportColumn("date", "Fecha", "datetime"),
            ReportColumn("action", "Acción", "text"),
            ReportColumn("entity_type", "Entidad", "text"),
            ReportColumn("entity_id", "ID", "integer"),
            ReportColumn("user", "Usuario", "text"),
            ReportColumn("details", "Detalle", "text"),
        ),
        search_placeholder="Buscar acción, entidad, usuario, detalle...",
    ),
)

REPORT_BY_KEY = {definition.key: definition for definition in REPORT_DEFINITIONS}
