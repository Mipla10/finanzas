"""Reloj inyectable: la única forma de saber «ahora» y «hoy» (plan §5.5).

El código nunca llama a date.today() ni datetime.now() directamente; recibe
un Clock. En producción es SystemClock; en los tests, FixedClock.
"""

from datetime import date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

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
