"""Saldos derivados, subtotales y advertencias (RF-14 a RF-16, plan §3.1–§3.4).

El saldo NUNCA se guarda: siempre es saldo inicial + entradas − salidas,
contando solo los movimientos vigentes (principio 3).
"""

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from finanzas.domain.accounts import AccountType
from finanzas.domain.messages import render


@dataclass(frozen=True)
class AccountInfo:
    """Lo que el cálculo de saldos necesita saber de una cuenta."""

    id: uuid.UUID
    name: str
    type: AccountType
    parent_id: uuid.UUID | None
    initial_balance_cents: int
    archived: bool = False


@dataclass(frozen=True)
class Flow:
    """El efecto de un movimiento: sale de `from`, entra a `to`."""

    from_account_id: uuid.UUID | None
    to_account_id: uuid.UUID | None
    amount_cents: int
    voided: bool = False


def compute_balances(
    accounts: Iterable[AccountInfo], flows: Iterable[Flow]
) -> dict[uuid.UUID, int]:
    """Saldo actual de cada cuenta (plan §3.1)."""
    balances = {account.id: account.initial_balance_cents for account in accounts}
    for flow in flows:
        if flow.voided:
            continue  # los anulados no cuentan
        if flow.to_account_id in balances:
            balances[flow.to_account_id] += flow.amount_cents
        if flow.from_account_id in balances:
            balances[flow.from_account_id] -= flow.amount_cents
    return balances


@dataclass(frozen=True)
class AccountBalance:
    account_id: uuid.UUID
    name: str
    type: AccountType
    parent_id: uuid.UUID | None
    archived: bool
    balance_cents: int


@dataclass(frozen=True)
class BankGroup:
    bank_id: uuid.UUID
    name: str
    subtotal_cents: int


@dataclass(frozen=True)
class BalanceSummary:
    accounts: list[AccountBalance]
    groups: list[BankGroup]
    total_cents: int


def summarize_balances(
    accounts: Sequence[AccountInfo], balances: Mapping[uuid.UUID, int]
) -> BalanceSummary:
    """Cuentas visibles, subtotal «banco + bolsillos» y total (plan §3.2)."""
    visible = [
        AccountBalance(a.id, a.name, a.type, a.parent_id, a.archived, balances[a.id])
        for a in accounts
        if not a.archived or balances[a.id] != 0
    ]
    groups = []
    for bank in accounts:
        if bank.type is not AccountType.BANK:
            continue
        pockets = [a for a in accounts if a.parent_id == bank.id]
        if pockets:
            subtotal = balances[bank.id] + sum(balances[p.id] for p in pockets)
            groups.append(BankGroup(bank.id, bank.name, subtotal))
    # Cada cuenta una sola vez, incluidas las archivadas (que suelen estar en 0).
    total = sum(balances[a.id] for a in accounts)
    return BalanceSummary(visible, groups, total)


@dataclass(frozen=True)
class BalanceWarning:
    code: str
    account_id: uuid.UUID
    account_name: str
    balance_cents: int
    message: str


def detect_warnings(
    affected: Iterable[AccountInfo], balances: Mapping[uuid.UUID, int]
) -> list[BalanceWarning]:
    """Avisos para las cuentas que tocó una operación (plan §3.4)."""
    warnings: list[BalanceWarning] = []
    seen: set[uuid.UUID] = set()
    for account in affected:
        if account.id in seen:
            continue
        seen.add(account.id)
        balance = balances[account.id]
        if balance < 0:
            warnings.append(_warning("negative_balance", account, balance))
        if account.archived and balance != 0:
            warnings.append(_warning("archived_nonzero_balance", account, balance))
    return warnings


def _warning(code: str, account: AccountInfo, balance: int) -> BalanceWarning:
    return BalanceWarning(
        code=code,
        account_id=account.id,
        account_name=account.name,
        balance_cents=balance,
        message=render(code, account=account.name),
    )
