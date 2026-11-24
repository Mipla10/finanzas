"""Cálculo del ajuste al saldo real del banco (RF-12, plan §3.3).

El monto del ajuste es siempre positivo; la dirección dice si suma o resta.
"""

from dataclasses import dataclass

from finanzas.domain.money import validate_amount, validate_balance
from finanzas.domain.movements import AdjustmentDirection

FIELD = "real_balance_cents"


@dataclass(frozen=True)
class Adjustment:
    direction: AdjustmentDirection
    amount_cents: int


def compute_adjustment(current_cents: int, real_cents: int) -> Adjustment | None:
    """Ajuste necesario para que la cuenta muestre `real_cents`.

    None si ya cuadra (CL-14): en ese caso no se crea ningún movimiento.
    """
    real = validate_balance(real_cents, field=FIELD)
    difference = real - current_cents
    if difference == 0:
        return None
    direction = AdjustmentDirection.IN if difference > 0 else AdjustmentDirection.OUT
    return Adjustment(direction, validate_amount(abs(difference), field=FIELD))
