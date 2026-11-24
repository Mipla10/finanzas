"""Consultas de cuentas, siempre limitadas al dueño (RNF-5)."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from finanzas.db.models import Account


def get_owned(
    session: Session, owner_id: uuid.UUID, account_id: uuid.UUID
) -> Account | None:
    """La cuenta si existe Y es del dueño; si es de otro, como si no existiera."""
    return session.scalar(
        select(Account).where(Account.id == account_id, Account.owner_id == owner_id)
    )


def name_taken(session: Session, owner_id: uuid.UUID, name_key: str) -> bool:
    query = select(Account.id).where(
        Account.owner_id == owner_id, Account.name_key == name_key
    )
    return bool(session.scalar(select(exists(query))))


def list_owned(
    session: Session, owner_id: uuid.UUID, include_archived: bool
) -> list[Account]:
    query = select(Account).where(Account.owner_id == owner_id)
    if not include_archived:
        query = query.where(Account.archived_at.is_(None))
    return list(session.scalars(query.order_by(Account.created_at, Account.name_key)))
