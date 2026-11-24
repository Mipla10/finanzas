"""Ajuste de saldo al valor real del banco (RF-12, plan §3.3)."""

import uuid
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from finanzas.db.models import Movement
from finanzas.db.repositories import accounts as accounts_repo
from finanzas.db.repositories.balances import balances_for_owner
from finanzas.domain.adjustments import compute_adjustment
from finanzas.domain.balances import BalanceWarning
from finanzas.domain.dates import Clock
from finanzas.domain.errors import Conflict, NotFound
from finanzas.domain.movements import AdjustmentDirection, MovementType
from finanzas.services.movements import insert_with_first_version
from finanzas.services.warnings import warnings_for


@dataclass(frozen=True)
class AdjustmentResult:
    status: Literal["adjusted", "already_balanced"]
    movement: Movement | None
    balance_cents: int  # saldo de la cuenta después de la operación
    warnings: list[BalanceWarning] = field(default_factory=list)


def adjust_balance(
    session: Session,
    owner_id: uuid.UUID,
    clock: Clock,
    account_id: uuid.UUID,
    *,
    real_balance_cents: int,
) -> AdjustmentResult:
    """Cuadra la cuenta con el saldo que muestra el banco HOY.

    Compara con el saldo PROPIO (un banco, sin sus bolsillos). Si ya cuadra,
    no crea nada. La fila de la cuenta queda bloqueada hasta el final: dos
    ajustes simultáneos se aplican uno tras otro (varios en un día, RF-12).
    """
    account = accounts_repo.get_owned_for_update(session, owner_id, account_id)
    if account is None:
        raise NotFound("resource_not_found", field="account_id")
    if account.archived_at is not None:
        raise Conflict("account_archived", field="account_id")

    current = balances_for_owner(session, owner_id, [account.id])[account.id]
    adjustment = compute_adjustment(current, real_balance_cents)
    if adjustment is None:
        session.commit()  # libera el bloqueo
        return AdjustmentResult("already_balanced", None, current)

    goes_in = adjustment.direction is AdjustmentDirection.IN
    movement = insert_with_first_version(
        session,
        owner_id,
        clock,
        MovementType.ADJUSTMENT,
        adjustment_direction=adjustment.direction,
        amount_cents=adjustment.amount_cents,
        date=clock.today(),  # los ajustes son siempre de hoy (RF-12)
        from_account_id=None if goes_in else account.id,
        to_account_id=account.id if goes_in else None,
        category_id=None,
        merchant=None,
        merchant_key=None,
        note=None,
    )
    warnings = warnings_for(session, owner_id, [account])
    session.commit()
    return AdjustmentResult("adjusted", movement, real_balance_cents, warnings)
