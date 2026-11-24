"""Esquemas del ajuste de saldo (RF-12, plan §4.3)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from finanzas.api.schemas.common import Cents, RequestModel
from finanzas.api.schemas.movements import MovementOut, WarningOut


class AdjustmentRequest(RequestModel):
    """Solo el saldo real de HOY: no se admite fecha (CL-17)."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"real_balance_cents": 17150000}]}
    )

    real_balance_cents: Cents  # puede ser cero o negativo


class AdjustedOut(BaseModel):
    """201: se creó un movimiento de ajuste."""

    status: Literal["adjusted"]
    movement: MovementOut
    warnings: list[WarningOut]


class AlreadyBalancedOut(BaseModel):
    """200: la cuenta ya cuadra; no se creó nada (CL-14)."""

    status: Literal["already_balanced"]
    movement: None
    balance_cents: int
    warnings: list[WarningOut]
