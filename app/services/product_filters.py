"""Typed specifications for advanced product catalogue filtering.

The GUI builds these immutable specifications while ProductService translates
 them into SQLAlchemy expressions. Keeping the specification outside the Qt
 layer makes the filtering reusable for reports, APIs and future views.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


PRODUCT_SORT_FIELDS = {
    "id": "id",
    "sku": "sku",
    "name": "name",
    "category": "category",
    "brand": "brand",
    "sale_price": "sale_price",
    "stock_current": "stock_current",
    "stock_min": "stock_min",
    "created_at": "created_at",
}

STOCK_FILTERS = {"all", "in_stock", "low", "out"}
SORT_DIRECTIONS = {"asc", "desc"}


@dataclass(frozen=True, slots=True)
class ProductFilter:
    """Complete product catalogue filter and ordering specification."""

    search: str = ""
    product_id: int | None = None
    id_min: int | None = None
    id_max: int | None = None
    category: str | None = None
    brand: str | None = None
    active: bool | None = None
    stock_status: str = "all"
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    sort_by: str = "id"
    sort_direction: str = "asc"

    def __post_init__(self) -> None:
        object.__setattr__(self, "search", (self.search or "").strip())
        object.__setattr__(self, "category", self._clean_optional(self.category))
        object.__setattr__(self, "brand", self._clean_optional(self.brand))
        object.__setattr__(self, "stock_status", (self.stock_status or "all").strip().lower())
        object.__setattr__(self, "sort_by", (self.sort_by or "id").strip())
        object.__setattr__(self, "sort_direction", (self.sort_direction or "asc").strip().lower())
        if self.product_id is not None:
            object.__setattr__(self, "product_id", int(self.product_id))
        if self.id_min is not None:
            object.__setattr__(self, "id_min", int(self.id_min))
        if self.id_max is not None:
            object.__setattr__(self, "id_max", int(self.id_max))
        if self.stock_status not in STOCK_FILTERS:
            raise ValueError("Filtro de stock no válido.")
        if self.sort_by not in PRODUCT_SORT_FIELDS:
            raise ValueError("Campo de ordenamiento no válido.")
        if self.sort_direction not in SORT_DIRECTIONS:
            raise ValueError("Dirección de ordenamiento no válida.")
        if self.product_id is not None and self.product_id < 1:
            raise ValueError("El ID del producto debe ser mayor que cero.")
        if self.id_min is not None and self.id_min < 1:
            raise ValueError("El ID mínimo debe ser mayor que cero.")
        if self.id_max is not None and self.id_max < 1:
            raise ValueError("El ID máximo debe ser mayor que cero.")
        if self.id_min is not None and self.id_max is not None and self.id_min > self.id_max:
            raise ValueError("El rango de ID no es válido.")
        if self.price_min is not None and self.price_min < 0:
            raise ValueError("El precio mínimo no puede ser negativo.")
        if self.price_max is not None and self.price_max < 0:
            raise ValueError("El precio máximo no puede ser negativo.")
        if self.price_min is not None and self.price_max is not None and self.price_min > self.price_max:
            raise ValueError("El rango de precio no es válido.")
        if self.created_from is not None and self.created_to is not None and self.created_from > self.created_to:
            raise ValueError("El rango de fechas no es válido.")

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        value = (value or "").strip()
        return value or None

    @property
    def has_filters(self) -> bool:
        return any(
            (
                bool(self.search),
                self.product_id is not None,
                self.id_min is not None,
                self.id_max is not None,
                self.category is not None,
                self.brand is not None,
                self.active is not None,
                self.stock_status != "all",
                self.price_min is not None,
                self.price_max is not None,
                self.created_from is not None,
                self.created_to is not None,
            )
        )
