from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        value = 0
    if isinstance(value, float):
        raise TypeError("Los cálculos monetarios internos no aceptan float; usa Decimal, int o str.")
    if isinstance(value, str):
        raw = value.strip().replace("$", "").replace(" ", "")
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif raw.count(".") > 1:
            raw = raw.replace(".", "")
        value = raw or "0"
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"Importe inválido: {value!r}") from exc


def line_total(unit_price: Decimal, quantity: int, discount: Decimal = ZERO) -> Decimal:
    return money(money(unit_price) * quantity - money(discount))


def gross_profit(revenue: Decimal, cogs: Decimal) -> Decimal:
    return money(revenue - cogs)


def net_profit(gross: Decimal, shipping: Decimal, commission: Decimal, other_cost: Decimal) -> Decimal:
    return money(gross - shipping - commission - other_cost)


def pct(value: Decimal, base: Decimal) -> Decimal:
    if money(base) == ZERO:
        return ZERO
    return money((money(value) / money(base)) * Decimal("100"))


def sale_financials(subtotal: Decimal, discount: Decimal, shipping_charge: Decimal, cogs: Decimal,
                    shipping_cost: Decimal, shipping_payer: str, commission: Decimal,
                    other_cost: Decimal) -> dict[str, Decimal]:
    """Calcula el resumen financiero de una venta con una sola regla central."""
    subtotal = money(subtotal)
    discount = money(discount)
    shipping_charge = money(shipping_charge)
    cogs = money(cogs)
    shipping_cost = money(shipping_cost)
    commission = money(commission)
    other_cost = money(other_cost)
    if discount > subtotal:
        raise ValueError("El descuento global no puede superar el subtotal.")
    product_revenue = money(subtotal - discount)
    total = money(product_revenue + shipping_charge)
    shipping_expense = shipping_cost if shipping_payer in {"TIENDA", "CLIENTE"} else ZERO
    gross = gross_profit(total, cogs)
    net = net_profit(gross, shipping_expense, commission, other_cost)
    return {
        "product_revenue": product_revenue,
        "shipping_expense": money(shipping_expense),
        "total": total,
        "gross_profit": gross,
        "net_profit": net,
    }
