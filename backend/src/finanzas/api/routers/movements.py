"""Endpoints de movimientos (RF-7 a RF-11, RF-18, plan §4.2)."""

import uuid

from fastapi import APIRouter, status
from sqlalchemy.orm import Session

from finanzas.api.deps import ClockDep, OwnerDep, SessionDep
from finanzas.api.schemas.movements import (
    MovementCreate,
    MovementOut,
    MovementWithWarnings,
    WarningOut,
)
from finanzas.db.models import Movement
from finanzas.domain.balances import BalanceWarning
from finanzas.services import movements as service

router = APIRouter(prefix="/movements", tags=["movimientos"])


def movement_out(session: Session, owner_id: uuid.UUID, m: Movement) -> MovementOut:
    return MovementOut.of(m, service.names_for(session, owner_id, [m]))


def with_warnings(
    session: Session,
    owner_id: uuid.UUID,
    m: Movement,
    warnings: list[BalanceWarning],
) -> MovementWithWarnings:
    return MovementWithWarnings(
        movement=movement_out(session, owner_id, m),
        warnings=[WarningOut.of(w) for w in warnings],
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Crear gasto, ingreso, transferencia o rendimiento",
)
def create_movement(
    body: MovementCreate, session: SessionDep, owner_id: OwnerDep, clock: ClockDep
) -> MovementWithWarnings:
    result = service.create_movement(
        session,
        owner_id,
        clock,
        movement_type=body.type,
        amount_cents=body.amount_cents,
        on=body.date,
        from_account_id=body.from_account_id,
        to_account_id=body.to_account_id,
        category_id=body.category_id,
        merchant=body.merchant,
        note=body.note,
    )
    return with_warnings(session, owner_id, result.movement, result.warnings)


@router.get("/{movement_id}", summary="Ver movimiento")
def get_movement(
    movement_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> MovementOut:
    return movement_out(
        session, owner_id, service.get_movement(session, owner_id, movement_id)
    )
