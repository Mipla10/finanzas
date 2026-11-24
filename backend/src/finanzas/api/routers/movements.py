"""Endpoints de movimientos (RF-7 a RF-11, RF-18, plan §4.2)."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Query, status
from sqlalchemy.orm import Session

from finanzas.api.deps import ClockDep, OwnerDep, SessionDep
from finanzas.api.schemas.errors import error_responses
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
    response_description="Movimiento creado.",
    responses=error_responses(404, 409, 422),
)
def create_movement(
    body: MovementCreate, session: SessionDep, owner_id: OwnerDep, clock: ClockDep
) -> MovementWithWarnings:
    """Registra un gasto, ingreso, transferencia o rendimiento (RF-7 a RF-11). Los
    montos son centavos enteros y positivos. Sin `date`, se usa hoy en Bogotá. Si una
    cuenta queda en negativo, se guarda igual y se devuelve una advertencia (RF-14).
    Los ajustes se hacen en `/accounts/{id}/adjustments`.
    """
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


@router.get(
    "",
    summary="Listar y filtrar movimientos, con totales",
    response_description="Página de movimientos y totales.",
    responses=error_responses(404, 422),
)
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
    """Lista los movimientos del más reciente al más antiguo (RF-17). `account_id`,
    `category_id` y `type` se pueden repetir. Los totales cubren todo el filtro, no
    solo la página; transferencias, ajustes y anulados no suman.
    """
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


@router.get(
    "/{movement_id}",
    summary="Ver movimiento",
    response_description="El movimiento.",
    responses=error_responses(404, 422),
)
def get_movement(
    movement_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> MovementOut:
    """Devuelve todos los datos de un movimiento y su estado: vigente o
    anulado (RF-18).
    """
    return movement_out(
        session, owner_id, service.get_movement(session, owner_id, movement_id)
    )


# Nombre del campo en el JSON → nombre del parámetro en el servicio.
_CORRECTION_PARAMS = {"type": "movement_type", "date": "on"}


@router.patch(
    "/{movement_id}",
    summary="Corregir movimiento",
    response_description="Resultado de la corrección.",
    responses=error_responses(404, 409, 422),
)
def correct_movement(
    movement_id: uuid.UUID,
    body: MovementCorrection,
    session: SessionDep,
    owner_id: OwnerDep,
    clock: ClockDep,
) -> CorrectionOut:
    """Corrige un movimiento y guarda la versión anterior (RF-19). Solo cambia lo que se
    envía; `null` borra un dato opcional. No se puede cambiar el tipo ni corregir un
    ajuste o un anulado. Si nada cambia de verdad, responde `changed: false` y no
    crea versión.
    """
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


@router.post(
    "/{movement_id}/void",
    summary="Anular movimiento",
    response_description="Movimiento anulado.",
    responses=error_responses(404, 409, 422),
)
def void_movement(
    movement_id: uuid.UUID,
    session: SessionDep,
    owner_id: OwnerDep,
    clock: ClockDep,
    body: Annotated[VoidRequest | None, Body()] = None,
) -> MovementWithWarnings:
    """Anula un movimiento con un motivo opcional (RF-21). Deja de contar en saldos y
    totales, pero sigue consultable. Es definitivo.
    """
    reason = body.reason if body is not None else None
    result = service.void_movement(session, owner_id, clock, movement_id, reason=reason)
    return with_warnings(session, owner_id, result.movement, result.warnings)


@router.get(
    "/{movement_id}/history",
    summary="Historial de versiones",
    response_description="Historial del movimiento.",
    responses=error_responses(404, 422),
)
def get_history(
    movement_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> HistoryOut:
    """Todas las versiones en orden, con los campos que cambiaron, y al final la
    anulación si la hay (RF-20).
    """
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
