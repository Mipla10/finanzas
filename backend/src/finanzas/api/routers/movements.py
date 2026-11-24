"""Endpoints de movimientos (RF-7 a RF-11, RF-18, plan §4.2)."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy.orm import Session

from finanzas.api.deps import ClockDep, OwnerDep, SessionDep
from finanzas.api.schemas.movements import (
    MovementCreate,
    MovementListOut,
    MovementOut,
    MovementWithWarnings,
    PageOut,
    TotalsOut,
    WarningOut,
)
from finanzas.db.models import Movement
from finanzas.domain.balances import BalanceWarning
from finanzas.domain.movements import MovementType
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


@router.get("", summary="Listar y filtrar movimientos, con totales")
def list_movements(
    session: SessionDep,
    owner_id: OwnerDep,
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    category_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    type: Annotated[list[MovementType] | None, Query()] = None,
    include_voided: bool = False,
    limit: Annotated[int, Query(ge=1, le=service.MAX_LIMIT)] = service.DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MovementListOut:
    page = service.list_movements(
        session,
        owner_id,
        date_from=date_from,
        date_to=date_to,
        account_ids=account_id,
        category_ids=category_id,
        types=type,
        include_voided=include_voided,
        limit=limit,
        offset=offset,
    )
    names = service.names_for(session, owner_id, page.items)
    t = page.totals
    return MovementListOut(
        items=[MovementOut.of(m, names) for m in page.items],
        totals=TotalsOut(
            income_cents=t.income_cents,
            yield_cents=t.yield_cents,
            expense_cents=t.expense_cents,
            net_cents=t.net_cents,
        ),
        page=PageOut(
            limit=page.limit, offset=page.offset, total_items=page.total_items
        ),
    )


@router.get("/{movement_id}", summary="Ver movimiento")
def get_movement(
    movement_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> MovementOut:
    return movement_out(
        session, owner_id, service.get_movement(session, owner_id, movement_id)
    )
