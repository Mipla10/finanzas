"""Consultas de cuentas, siempre limitadas al dueño (RNF-5)."""

import uuid

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Movement, MovementVersion


def get_owned(
    session: Session, owner_id: uuid.UUID, account_id: uuid.UUID
) -> Account | None:
    """La cuenta si existe Y es del dueño; si es de otro, como si no existiera."""
    return session.scalar(
        select(Account).where(Account.id == account_id, Account.owner_id == owner_id)
    )


def name_taken(
    session: Session,
    owner_id: uuid.UUID,
    name_key: str,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    """¿Otra cuenta del dueño usa ese nombre? `exclude_id`: la propia (renombrar)."""
    query = select(Account.id).where(
        Account.owner_id == owner_id, Account.name_key == name_key
    )
    if exclude_id is not None:
        query = query.where(Account.id != exclude_id)
    return bool(session.scalar(select(exists(query))))


def used_by_movements(
    session: Session, owner_id: uuid.UUID, account_id: uuid.UUID
) -> bool:
    """¿Algún movimiento (anulados incluidos) o versión anterior la usa? (plan §3.8)"""
    in_movements = select(Movement.id).where(
        Movement.owner_id == owner_id,
        or_(
            Movement.from_account_id == account_id,
            Movement.to_account_id == account_id,
        ),
    )
    in_versions = select(MovementVersion.id).where(
        MovementVersion.owner_id == owner_id,
        or_(
            MovementVersion.from_account_id == account_id,
            MovementVersion.to_account_id == account_id,
        ),
    )
    return bool(session.scalar(select(exists(in_movements) | exists(in_versions))))


def list_owned(
    session: Session, owner_id: uuid.UUID, include_archived: bool
) -> list[Account]:
    query = select(Account).where(Account.owner_id == owner_id)
    if not include_archived:
        query = query.where(Account.archived_at.is_(None))
    return list(session.scalars(query.order_by(Account.created_at, Account.name_key)))


def active_pockets(
    session: Session, owner_id: uuid.UUID, bank_id: uuid.UUID
) -> list[Account]:
    query = select(Account).where(
        Account.owner_id == owner_id,
        Account.parent_id == bank_id,
        Account.archived_at.is_(None),
    )
    return list(session.scalars(query.order_by(Account.name_key)))


def has_pockets(session: Session, owner_id: uuid.UUID, account_id: uuid.UUID) -> bool:
    """¿Es padre de algún bolsillo, activo o archivado?"""
    query = select(Account.id).where(
        Account.owner_id == owner_id, Account.parent_id == account_id
    )
    return bool(session.scalar(select(exists(query))))
