"""Dinero exacto: enteros en centavos de COP (principio 2, RF-1).

Nunca float: 2500.5 o 2500.0 se rechazan. Ejemplo: $ 25.000 = 2500000.
"""

from typing import Any

from finanzas.domain.errors import InvalidData

# Mayor entero que JavaScript representa sin error (≈ 90 billones de pesos).
MAX_CENTS = 2**53 - 1


def _check_integer_in_range(value: Any, field: str) -> int:
    # bool es subclase de int en Python (True == 1): no es un monto.
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidData("amount_not_integer", field=field)
    if abs(value) > MAX_CENTS:
        raise InvalidData(
            "amount_too_large", field=field, max=f"{MAX_CENTS:,}".replace(",", ".")
        )
    return value


def validate_amount(value: Any, field: str = "amount_cents") -> int:
    """Monto de un movimiento: entero de centavos, mayor que cero."""
    amount = _check_integer_in_range(value, field)
    if amount <= 0:
        raise InvalidData("amount_not_positive", field=field)
    return amount


def validate_balance(value: Any, field: str) -> int:
    """Saldo (inicial o real de un ajuste): entero, puede ser cero o negativo."""
    return _check_integer_in_range(value, field)
