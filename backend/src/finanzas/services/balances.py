"""«¿Cuánto tengo?»: saldos, subtotales y total (RF-15, RF-16, plan §3.2)."""

import uuid

from sqlalchemy.orm import Session

from finanzas.db.repositories import accounts as accounts_repo
from finanzas.db.repositories.balances import balances_for_owner
from finanzas.domain.balances import AccountInfo, BalanceSummary, summarize_balances


def get_balances(session: Session, owner_id: uuid.UUID) -> BalanceSummary:
    """Saldo de cada cuenta del dueño, subtotal «banco + bolsillos» y total.

    Incluye las archivadas: suman al total y se muestran solo si su saldo no
    es cero. Los saldos los calcula la BD en una consulta (DT-1).
    """
    accounts = accounts_repo.list_owned(session, owner_id, include_archived=True)
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
    return summarize_balances(infos, balances_for_owner(session, owner_id))
