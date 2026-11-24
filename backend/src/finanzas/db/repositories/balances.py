"""Saldos calculados por la BD en UNA consulta (plan §3.1, DT-1).

Misma fórmula que domain/balances.compute_balances; un test de propiedades
comprueba que ambas coinciden siempre.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import BigInteger, cast, func, select, union_all
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Movement


def balances_for_owner(
    session: Session,
    owner_id: uuid.UUID,
    account_ids: Iterable[uuid.UUID] | None = None,
) -> dict[uuid.UUID, int]:
    """{cuenta: saldo actual} de las cuentas del dueño (o solo de `account_ids`)."""
    active = (Movement.owner_id == owner_id, Movement.voided_at.is_(None))
    flows = union_all(
        # Lo que entra suma…
        select(
            Movement.to_account_id.label("account_id"),
            Movement.amount_cents.label("delta"),
        ).where(*active, Movement.to_account_id.is_not(None)),
        # …y lo que sale resta.
        select(
            Movement.from_account_id.label("account_id"),
            (-Movement.amount_cents).label("delta"),
        ).where(*active, Movement.from_account_id.is_not(None)),
    ).subquery()

    # SUM de BIGINT devuelve NUMERIC en PostgreSQL: se vuelve a BIGINT (entero exacto).
    total_delta = cast(func.coalesce(func.sum(flows.c.delta), 0), BigInteger)
    query = (
        select(Account.id, Account.initial_balance_cents + total_delta)
        .outerjoin(flows, flows.c.account_id == Account.id)
        .where(Account.owner_id == owner_id)
        .group_by(Account.id)
    )
    if account_ids is not None:
        query = query.where(Account.id.in_(list(account_ids)))
    return {account_id: balance for account_id, balance in session.execute(query)}
