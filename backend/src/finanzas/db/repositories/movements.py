"""Consultas de movimientos, siempre limitadas al dueño (RNF-5)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, MovementVersion


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
