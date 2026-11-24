"""Endpoints de movimientos (RF-7 a RF-11, RF-18, plan §4.2)."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Query, status
from sqlalchemy.orm import Session

from finanzas.api.deps import ClockDep, OwnerDep, SessionDep
from finanzas.api.schemas.movements import (
    CorrectionOut,
    HistoryOut,
    MovementCorrection,
    MovementCreate,
    MovementListOut,
    MovementOut,
    MovementWithWarnings,
    NamedRef,
    PageOut,
    TotalsOut,
    VersionOut,
    VoidedOut,
    VoidRequest,
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


# Nombre del campo en el JSON → nombre del parámetro en el servicio.
_CORRECTION_PARAMS = {"type": "movement_type", "date": "on"}


@router.patch("/{movement_id}", summary="Corregir movimiento")
def correct_movement(
    movement_id: uuid.UUID,
    body: MovementCorrection,
    session: SessionDep,
    owner_id: OwnerDep,
    clock: ClockDep,
) -> CorrectionOut:
    # Solo lo que vino en el JSON: lo ausente no cambia; null sí cuenta.
    changes = {
        _CORRECTION_PARAMS.get(name, name): getattr(body, name)
        for name in body.model_fields_set
    }
    result = service.correct_movement(session, owner_id, clock, movement_id, **changes)
    return CorrectionOut(
        movement=movement_out(session, owner_id, result.movement),
        changed=result.changed,
        warnings=[WarningOut.of(w) for w in result.warnings],
    )


@router.post("/{movement_id}/void", summary="Anular movimiento")
def void_movement(
    movement_id: uuid.UUID,
    session: SessionDep,
    owner_id: OwnerDep,
    clock: ClockDep,
    body: Annotated[VoidRequest | None, Body()] = None,
) -> MovementWithWarnings:
    reason = body.reason if body is not None else None
    result = service.void_movement(session, owner_id, clock, movement_id, reason=reason)
    return with_warnings(session, owner_id, result.movement, result.warnings)


@router.get("/{movement_id}/history", summary="Historial de versiones")
def get_history(
    movement_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> HistoryOut:
    history = service.get_history(session, owner_id, movement_id)

    def ref(item: service.NamedRef | None) -> NamedRef | None:
        return NamedRef(id=item.id, name=item.name) if item is not None else None

    return HistoryOut(
        movement_id=history.movement_id,
        versions=[
            VersionOut(
                version=v.version,
                created_at=v.created_at,
                changed_fields=v.changed_fields,
                amount_cents=v.amount_cents,
                date=v.date,
                from_account=ref(v.from_account),
                to_account=ref(v.to_account),
                category=ref(v.category),
                merchant=v.merchant,
                note=v.note,
            )
            for v in history.versions
        ],
        voided=VoidedOut(at=history.voided.at, reason=history.voided.reason)
        if history.voided is not None
        else None,
    )
