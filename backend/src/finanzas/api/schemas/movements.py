"""Esquemas de movimientos (RF-7 a RF-11, RF-14, RF-18, plan §4.3)."""

import datetime as dt
import uuid
from collections.abc import Mapping

from pydantic import BaseModel

from finanzas.api.schemas.common import BogotaDatetime, Cents, RequestModel
from finanzas.db.models import Movement
from finanzas.domain.balances import BalanceWarning
from finanzas.domain.movements import AdjustmentDirection, MovementType


class NamedRef(BaseModel):
    """Una cuenta o categoría con su nombre ACTUAL (decisión C-5)."""

    id: uuid.UUID
    name: str


def named(item_id: uuid.UUID | None, names: Mapping[uuid.UUID, str]) -> NamedRef | None:
    return NamedRef(id=item_id, name=names[item_id]) if item_id is not None else None


class MovementCreate(RequestModel):
    """Gasto, ingreso, transferencia o rendimiento. Los ajustes van aparte."""

    type: MovementType
    amount_cents: Cents
    date: dt.date | None = None  # por defecto, hoy en Bogotá
    from_account_id: uuid.UUID | None = None
    to_account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    merchant: str | None = None
    note: str | None = None


class MovementOut(BaseModel):
    id: uuid.UUID
    type: MovementType
    amount_cents: int
    date: dt.date
    from_account: NamedRef | None
    to_account: NamedRef | None
    category: NamedRef | None
    adjustment_direction: AdjustmentDirection | None
    merchant: str | None
    note: str | None
    voided: bool
    voided_at: BogotaDatetime | None
    void_reason: str | None
    version: int
    created_at: BogotaDatetime

    @classmethod
    def of(cls, m: Movement, names: Mapping[uuid.UUID, str]) -> "MovementOut":
        return cls(
            id=m.id,
            type=m.type,
            amount_cents=m.amount_cents,
            date=m.date,
            from_account=named(m.from_account_id, names),
            to_account=named(m.to_account_id, names),
            category=named(m.category_id, names),
            adjustment_direction=m.adjustment_direction,
            merchant=m.merchant,
            note=m.note,
            voided=m.voided_at is not None,
            voided_at=m.voided_at,
            void_reason=m.void_reason,
            version=m.current_version,
            created_at=m.created_at,
        )


class WarningOut(BaseModel):
    """Aviso de saldo (RF-14): la operación se guardó igual."""

    code: str
    account: NamedRef
    balance_cents: int
    message: str

    @classmethod
    def of(cls, warning: BalanceWarning) -> "WarningOut":
        return cls(
            code=warning.code,
            account=NamedRef(id=warning.account_id, name=warning.account_name),
            balance_cents=warning.balance_cents,
            message=warning.message,
        )


class MovementWithWarnings(BaseModel):
    movement: MovementOut
    warnings: list[WarningOut]


class TotalsOut(BaseModel):
    """Totales del filtro completo, no solo de la página (RF-17)."""

    income_cents: int  # incluye los rendimientos
    yield_cents: int
    expense_cents: int
    net_cents: int


class PageOut(BaseModel):
    limit: int
    offset: int
    total_items: int


class MovementListOut(BaseModel):
    items: list[MovementOut]
    totals: TotalsOut
    page: PageOut


class MovementCorrection(RequestModel):
    """Solo cambia lo que se envía; `null` borra un dato opcional (RF-19).

    `type` se admite solo para rechazar con claridad un cambio de tipo (CL-21).
    """

    type: MovementType | None = None
    amount_cents: Cents | None = None
    date: dt.date | None = None
    from_account_id: uuid.UUID | None = None
    to_account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    merchant: str | None = None
    note: str | None = None


class CorrectionOut(BaseModel):
    movement: MovementOut
    changed: bool  # false: no hubo cambios reales y no se creó versión
    warnings: list[WarningOut]


class VoidRequest(RequestModel):
    reason: str | None = None


class VersionOut(BaseModel):
    version: int
    created_at: BogotaDatetime
    changed_fields: list[str]
    amount_cents: int
    date: dt.date
    from_account: NamedRef | None
    to_account: NamedRef | None
    category: NamedRef | None
    merchant: str | None
    note: str | None


class VoidedOut(BaseModel):
    at: BogotaDatetime
    reason: str | None


class HistoryOut(BaseModel):
    movement_id: uuid.UUID
    versions: list[VersionOut]
    voided: VoidedOut | None
