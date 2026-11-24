"""Piezas comunes de los esquemas (plan §4.1)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer, StrictInt

from finanzas.domain.dates import BOGOTA

# Centavos: entero ESTRICTO. 2500.5, "2500000" y 2.5e6 → 422 (plan §4.1).
# El límite de 2^53 − 1 y el signo los valida el dominio (domain/money.py).
Cents = StrictInt

# Marcas de tiempo en ISO 8601 con la zona de Bogotá: "2026-11-23T10:15:00-05:00".
BogotaDatetime = Annotated[
    datetime,
    PlainSerializer(lambda value: value.astimezone(BOGOTA).isoformat(), str),
]


class RequestModel(BaseModel):
    """Cuerpo de una petición: un campo desconocido es un error, no se ignora."""

    model_config = ConfigDict(extra="forbid")
