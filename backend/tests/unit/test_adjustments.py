"""T21: cálculo del ajuste al saldo real (RF-12, CL-14, CL-16, plan §3.3)."""

from typing import Any

import pytest

from finanzas.domain.adjustments import Adjustment, compute_adjustment
from finanzas.domain.errors import InvalidData
from finanzas.domain.money import MAX_CENTS
from finanzas.domain.movements import AdjustmentDirection


def test_cl_14_no_adjustment_when_real_balance_matches() -> None:
    assert compute_adjustment(current_cents=17150000, real_cents=17150000) is None


def test_real_balance_higher_means_money_in() -> None:
    assert compute_adjustment(current_cents=1000, real_cents=1500) == Adjustment(
        direction=AdjustmentDirection.IN, amount_cents=500
    )


def test_real_balance_lower_means_money_out() -> None:
    # Plan §2.4, M8: Nequi calculaba 17500000 y el banco mostraba 17150000.
    assert compute_adjustment(current_cents=17500000, real_cents=17150000) == (
        Adjustment(direction=AdjustmentDirection.OUT, amount_cents=350000)
    )


def test_cl_16_negative_real_balance_from_zero() -> None:
    assert compute_adjustment(current_cents=0, real_cents=-500000) == Adjustment(
        direction=AdjustmentDirection.OUT, amount_cents=500000
    )


def test_from_negative_back_to_zero_is_money_in() -> None:
    assert compute_adjustment(current_cents=-250000, real_cents=0) == Adjustment(
        direction=AdjustmentDirection.IN, amount_cents=250000
    )


@pytest.mark.parametrize("real", [10.5, "17150000", None, True])
def test_real_balance_must_be_integer_cents(real: Any) -> None:
    with pytest.raises(InvalidData) as caught:
        compute_adjustment(current_cents=0, real_cents=real)
    assert (caught.value.code, caught.value.field) == (
        "amount_not_integer",
        "real_balance_cents",
    )


def test_difference_beyond_technical_limit_is_rejected() -> None:
    with pytest.raises(InvalidData) as caught:
        compute_adjustment(current_cents=MAX_CENTS, real_cents=-1)
    assert (caught.value.code, caught.value.field) == (
        "amount_too_large",
        "real_balance_cents",
    )
