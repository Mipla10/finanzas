"""T16: montos en centavos (RF-1, CL-11, CL-12, CL-13, plan §4.1)."""

from typing import Any

import pytest

from finanzas.domain.errors import InvalidData
from finanzas.domain.money import MAX_CENTS, validate_amount, validate_balance


def test_max_is_the_largest_integer_a_browser_represents_exactly() -> None:
    assert MAX_CENTS == 2**53 - 1 == 9_007_199_254_740_991


# --- Montos de movimientos: enteros > 0 ---


@pytest.mark.parametrize("amount", [1, 123456, 2500000, MAX_CENTS])
def test_valid_amounts_are_returned_unchanged(amount: int) -> None:
    assert validate_amount(amount) == amount


def test_cl_12_yield_with_cents_is_exact() -> None:
    # CL-12: un rendimiento de $ 1.234,56 = 123456 centavos, sin redondeos.
    assert validate_amount(123456) == 123456


@pytest.mark.parametrize(
    ("amount", "code"),
    [
        (0, "amount_not_positive"),
        (-500000, "amount_not_positive"),
        (2500.5, "amount_not_integer"),
        (2500.0, "amount_not_integer"),  # un float nunca es dinero, aunque sea exacto
        ("25.000", "amount_not_integer"),
        ("2500000", "amount_not_integer"),
        (None, "amount_not_integer"),
        (True, "amount_not_integer"),  # en Python True == 1: no es un monto
        (MAX_CENTS + 1, "amount_too_large"),
    ],
)
def test_cl_11_invalid_amounts_are_rejected(amount: Any, code: str) -> None:
    with pytest.raises(InvalidData) as caught:
        validate_amount(amount)
    assert caught.value.code == code
    assert caught.value.field == "amount_cents"


def test_field_name_can_be_chosen() -> None:
    with pytest.raises(InvalidData) as caught:
        validate_amount(0, field="commission_cents")
    assert caught.value.field == "commission_cents"


# --- Saldos: enteros, pueden ser 0 o negativos ---


@pytest.mark.parametrize("balance", [0, -500000, 150000000, MAX_CENTS, -MAX_CENTS])
def test_cl_13_balances_may_be_zero_or_negative(balance: int) -> None:
    assert validate_balance(balance, field="initial_balance_cents") == balance


@pytest.mark.parametrize(
    ("balance", "code"),
    [
        (MAX_CENTS + 1, "amount_too_large"),
        (-MAX_CENTS - 1, "amount_too_large"),
        (10.5, "amount_not_integer"),
        ("0", "amount_not_integer"),
        (False, "amount_not_integer"),
    ],
)
def test_invalid_balances_are_rejected(balance: Any, code: str) -> None:
    with pytest.raises(InvalidData) as caught:
        validate_balance(balance, field="real_balance_cents")
    assert caught.value.code == code
    assert caught.value.field == "real_balance_cents"
