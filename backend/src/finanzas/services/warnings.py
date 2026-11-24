"""Advertencias de saldo tras una operación (RF-14, plan §3.4).

Se calculan DENTRO de la transacción, después del cambio, para ver el estado
ya actualizado. Avisan, nunca bloquean.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from finanzas.db.models import Account
from finanzas.db.repositories.balances import balances_for_owner
from finanzas.domain.balances import AccountInfo, BalanceWarning, detect_warnings


def warnings_for(
    session: Session, owner_id: uuid.UUID, accounts: Sequence[Account]
) -> list[BalanceWarning]:
    """Advertencias de las cuentas que tocó una operación, en ese orden."""
    session.flush()
    balances = balances_for_owner(session, owner_id, [a.id for a in accounts])
    infos = [
        AccountInfo(
            a.id,
            a.name,
            a.type,
            a.parent_id,
            a.initial_balance_cents,
            archived=a.archived_at is not None,
        )
        for a in accounts
    ]
    return detect_warnings(infos, balances)
