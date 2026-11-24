"""Reloj inyectable: la única forma de saber «ahora» y «hoy» (plan §5.5).

El código nunca llama a date.today() ni datetime.now() directamente; recibe
un Clock. En producción es SystemClock; en los tests, FixedClock.
"""

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from finanzas.domain.errors import InvalidData

BOGOTA = ZoneInfo("America/Bogota")


class Clock(Protocol):
    def now(self) -> datetime:
        """Instante actual, con zona horaria de Bogotá."""
        ...

    def today(self) -> date:
        """Fecha de hoy en Bogotá."""
        ...


class SystemClock:
    """Reloj real."""

    def now(self) -> datetime:
        return datetime.now(BOGOTA)

    def today(self) -> date:
        return self.now().date()


class FixedClock:
    """Reloj detenido para tests; solo avanza con advance()."""

    def __init__(self, instant: datetime | str) -> None:
        if isinstance(instant, str):
            instant = datetime.fromisoformat(instant)
        if instant.tzinfo is None:
            raise ValueError("FixedClock necesita una fecha con zona horaria.")
        self._instant = instant.astimezone(BOGOTA)

    def now(self) -> datetime:
        return self._instant

    def today(self) -> date:
        return self._instant.date()

    def advance(self, delta: timedelta) -> None:
        self._instant += delta


# --- Reglas de fecha (RF-2, plan §3.5) ---


def _require_plain_date(value: date, field: str) -> date:
    # datetime es subclase de date en Python: los movimientos llevan solo fecha.
    if isinstance(value, datetime):
        raise InvalidData("date_invalid", field=field)
    return value


def validate_movement_date(
    value: date, *, today: date, account_starts: Mapping[str, date]
) -> date:
    """Ni futura, ni anterior al inicio de alguna cuenta involucrada.

    `account_starts` = {nombre de la cuenta: su fecha de inicio}. El día de
    inicio sí se acepta: el saldo inicial es el saldo al COMENZAR ese día.
    """
    _require_plain_date(value, "date")
    if value > today:
        raise InvalidData("date_in_future", field="date")
    for account, start in account_starts.items():
        if value < start:
            raise InvalidData(
                "date_before_account_start",
                field="date",
                account=account,
                start=start.isoformat(),
            )
    return value


def validate_start_date(value: date, *, today: date) -> date:
    """La fecha de inicio de una cuenta no puede ser futura (RF-4)."""
    _require_plain_date(value, "start_date")
    if value > today:
        raise InvalidData("start_date_in_future", field="start_date")
    return value
