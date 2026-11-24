"""Consultas de movimientos, siempre limitadas al dueño (RNF-5)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas.db.models import Movement


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
