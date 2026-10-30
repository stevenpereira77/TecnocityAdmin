"""Monetary primitives for the project.

Monetary primitives shared by business calculations. All financial services should
reuse these functions so conversion and rounding stay deterministic.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_decimal(value: object) -> Decimal:
    """Convert common numeric/text input to Decimal without binary float arithmetic."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        raise TypeError("Los importes monetarios no aceptan float; usa Decimal, int o texto.")
    if isinstance(value, str):
        normalized = value.strip().replace("$", "").replace(" ", "")
        if "," in normalized:
            normalized = normalized.replace(".", "").replace(",", ".")
        elif normalized.count(".") > 1:
            normalized = normalized.replace(".", "")
        return Decimal(normalized)
    raise TypeError(f"Valor monetario no soportado: {type(value).__name__}")


def quantize_money(value: object) -> Decimal:
    """Normalize monetary values to two decimals using HALF_UP."""
    return to_decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
