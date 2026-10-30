from decimal import Decimal

from app.utils.money import CENT, quantize_money, to_decimal


def test_decimal_conversion_does_not_use_binary_float_repr():
    assert to_decimal("10.1") == Decimal("10.1")


def test_money_utility_rejects_float_inputs():
    try:
        to_decimal(10.1)  # type: ignore[arg-type]
        assert False, "float must not enter monetary utilities"
    except TypeError as exc:
        assert "float" in str(exc)


def test_money_rounding_is_deterministic():
    assert quantize_money("100.005") == Decimal("100.01")
    assert quantize_money("100,005") == Decimal("100.01")
    assert CENT == Decimal("0.01")


def test_colombian_thousands_format_is_supported_without_float():
    from app.calculations.financial import money
    assert money("1.234.567,89") == Decimal("1234567.89")
