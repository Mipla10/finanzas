"""Consultas de movimientos, siempre limitadas al dueño (RNF-5)."""

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, MovementVersion
from finanzas.domain.movements import MovementType


def get_owned_for_update(
    session: Session, owner_id: uuid.UUID, movement_id: uuid.UUID
) -> Movement | None:
    """El movimiento del dueño, bloqueado hasta el fin de la transacción (DT-6).

    Dos correcciones simultáneas del mismo movimiento esperan su turno.
    """
    return session.scalar(
        select(Movement)
        .where(Movement.id == movement_id, Movement.owner_id == owner_id)
        .with_for_update()
    )


def get_owned(
    session: Session, owner_id: uuid.UUID, movement_id: uuid.UUID
) -> Movement | None:
    return session.scalar(
        select(Movement).where(
            Movement.id == movement_id, Movement.owner_id == owner_id
        )
    )


def versions_of(
    session: Session, owner_id: uuid.UUID, movement_id: uuid.UUID
) -> list[MovementVersion]:
    return list(
        session.scalars(
            select(MovementVersion)
            .where(
                MovementVersion.owner_id == owner_id,
                MovementVersion.movement_id == movement_id,
            )
            .order_by(MovementVersion.version_no)
        )
    )


def names_of(
    session: Session, owner_id: uuid.UUID, ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Nombre ACTUAL de cuentas y categorías del dueño (decisión C-5)."""
    names: dict[uuid.UUID, str] = {}
    for model in (Account, Category):
        rows = session.execute(
            select(model.id, model.name).where(
                model.owner_id == owner_id, model.id.in_(ids)
            )
        )
        names.update({row_id: name for row_id, name in rows})
    return names


def filter_conditions(
    owner_id: uuid.UUID,
    *,
    date_from: date | None,
    date_to: date | None,
    account_ids: Sequence[uuid.UUID] | None,
    category_ids: Sequence[uuid.UUID] | None,
    types: Sequence[MovementType] | None,
    include_voided: bool,
) -> list[ColumnElement[bool]]:
    """Filtro del listado (RF-17): «y» entre filtros, «o» dentro de cada uno.

    Se arma en UN solo lugar: el listado, el conteo y los totales lo comparten.
    """
    conditions: list[ColumnElement[bool]] = [Movement.owner_id == owner_id]
    if not include_voided:
        conditions.append(Movement.voided_at.is_(None))
    if date_from is not None:
        conditions.append(Movement.date >= date_from)  # extremos incluidos
    if date_to is not None:
        conditions.append(Movement.date <= date_to)
    if account_ids:  # la cuenta como origen O destino; sin sus bolsillos
        conditions.append(
            or_(
                Movement.from_account_id.in_(account_ids),
                Movement.to_account_id.in_(account_ids),
            )
        )
    if category_ids:
        conditions.append(Movement.category_id.in_(category_ids))
    if types:
        conditions.append(Movement.type.in_(types))
    return conditions


def list_page(
    session: Session,
    conditions: list[ColumnElement[bool]],
    *,
    limit: int,
    offset: int,
) -> list[Movement]:
    """Orden total y estable: fecha, momento de registro e id, descendentes."""
    query = (
        select(Movement)
        .where(*conditions)
        .order_by(Movement.date.desc(), Movement.created_at.desc(), Movement.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(query))


def count(session: Session, conditions: list[ColumnElement[bool]]) -> int:
    return (
        session.scalar(select(func.count()).select_from(Movement).where(*conditions))
        or 0
    )
