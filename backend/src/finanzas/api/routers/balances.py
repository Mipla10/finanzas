"""GET /balances: «¿cuánto tengo?» (RF-15, RF-16, plan §4.2)."""

from fastapi import APIRouter

from finanzas.api.deps import OwnerDep, SessionDep
from finanzas.api.schemas.balances import AccountBalanceOut, BalancesOut, BankGroupOut
from finanzas.services.balances import get_balances

router = APIRouter(tags=["saldos"])


@router.get("/balances", summary="Saldos por cuenta, subtotales y total")
def balances(session: SessionDep, owner_id: OwnerDep) -> BalancesOut:
    summary = get_balances(session, owner_id)
    return BalancesOut(
        accounts=[
            AccountBalanceOut(
                id=a.account_id,
                name=a.name,
                type=a.type,
                parent_id=a.parent_id,
                archived=a.archived,
                balance_cents=a.balance_cents,
            )
            for a in summary.accounts
        ],
        groups=[
            BankGroupOut(
                bank_id=g.bank_id, name=g.name, subtotal_cents=g.subtotal_cents
            )
            for g in summary.groups
        ],
        total_cents=summary.total_cents,
    )
