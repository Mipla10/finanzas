"""T20: saldo derivado, subtotal banco + bolsillos y total (RF-15, RF-16).

Usa el ejemplo de plan §2.4: los valores esperados están calculados a mano.
"""

import uuid
from dataclasses import replace

from finanzas.domain.accounts import AccountType
from finanzas.domain.balances import (
    AccountInfo,
    Flow,
    compute_balances,
    summarize_balances,
)

# --- Plan §2.4 ---
A1, A2, A3, A4 = (uuid.uuid4() for _ in range(4))
LULO = AccountInfo(A1, "Lulo", AccountType.BANK, None, 150000000)
AHORRO = AccountInfo(A2, "Ahorro", AccountType.POCKET, A1, 300000000)
NEQUI = AccountInfo(A3, "Nequi", AccountType.DIGITAL_WALLET, None, 20000000)
EFECTIVO = AccountInfo(A4, "Efectivo", AccountType.CASH, None, 5000000)
ACCOUNTS = [LULO, AHORRO, NEQUI, EFECTIVO]

FLOWS = [
    Flow(from_account_id=None, to_account_id=A1, amount_cents=200000000),  # M1 ingreso
    Flow(from_account_id=A3, to_account_id=None, amount_cents=2500000),  # M2 gasto (v2)
    Flow(from_account_id=A1, to_account_id=A4, amount_cents=20000000),  # M3 cajero
    Flow(from_account_id=A1, to_account_id=None, amount_cents=700000),  # M4 comisión
    Flow(from_account_id=A1, to_account_id=A2, amount_cents=50000000),  # M5 al bolsillo
    Flow(  # M6 gasto ANULADO: no cuenta
        from_account_id=A4, to_account_id=None, amount_cents=8000000, voided=True
    ),
    Flow(from_account_id=None, to_account_id=A2, amount_cents=1234567),  # M7 rendim.
    Flow(from_account_id=A3, to_account_id=None, amount_cents=350000),  # M8 ajuste out
]


def test_plan_example_balances_per_account() -> None:
    assert compute_balances(ACCOUNTS, FLOWS) == {
        A1: 279300000,
        A2: 351234567,
        A3: 17150000,
        A4: 25000000,
    }


def test_plan_example_subtotal_and_total() -> None:
    summary = summarize_balances(ACCOUNTS, compute_balances(ACCOUNTS, FLOWS))
    assert [(g.bank_id, g.name, g.subtotal_cents) for g in summary.groups] == [
        (A1, "Lulo", 630534567)
    ]
    assert summary.total_cents == 672684567
    assert [(a.account_id, a.balance_cents) for a in summary.accounts] == [
        (A1, 279300000),
        (A2, 351234567),
        (A3, 17150000),
        (A4, 25000000),
    ]


def test_account_without_movements_keeps_its_initial_balance() -> None:
    assert compute_balances([NEQUI], []) == {A3: 20000000}


def test_voided_movements_do_not_count() -> None:
    voided_income = Flow(None, A3, 99999, voided=True)
    assert compute_balances([NEQUI], [voided_income]) == {A3: 20000000}


def test_flows_of_unknown_accounts_are_ignored() -> None:
    # Un movimiento de otra cuenta no cambia nada (cada cuenta suma lo suyo).
    assert compute_balances([NEQUI], [Flow(None, uuid.uuid4(), 500)]) == {A3: 20000000}


def test_transfer_between_pockets_keeps_subtotal_and_total() -> None:
    a5 = uuid.uuid4()
    otro = AccountInfo(a5, "Otro bolsillo", AccountType.POCKET, A1, 0)
    accounts = [*ACCOUNTS, otro]
    before = summarize_balances(accounts, compute_balances(accounts, FLOWS))
    moved = [*FLOWS, Flow(A2, a5, 10000000)]
    after = summarize_balances(accounts, compute_balances(accounts, moved))
    assert after.groups[0].subtotal_cents == before.groups[0].subtotal_cents
    assert after.total_cents == before.total_cents


def test_archived_account_with_zero_balance_is_hidden_but_counted() -> None:
    a5 = uuid.uuid4()
    vieja = AccountInfo(a5, "Cuenta vieja", AccountType.CASH, None, 0, archived=True)
    accounts = [*ACCOUNTS, vieja]
    summary = summarize_balances(accounts, compute_balances(accounts, FLOWS))
    assert a5 not in {a.account_id for a in summary.accounts}
    assert summary.total_cents == 672684567


def test_archived_account_with_balance_is_shown_marked_and_counted() -> None:
    archived_nequi = replace(NEQUI, archived=True)
    accounts = [LULO, AHORRO, archived_nequi, EFECTIVO]
    summary = summarize_balances(accounts, compute_balances(accounts, FLOWS))
    shown = {a.account_id: a for a in summary.accounts}
    assert shown[A3].archived is True
    assert shown[A3].balance_cents == 17150000
    assert summary.total_cents == 672684567


def test_bank_without_pockets_has_no_group() -> None:
    summary = summarize_balances([NEQUI, LULO], {A3: 1, A1: 2})
    assert summary.groups == []
    assert summary.total_cents == 3
