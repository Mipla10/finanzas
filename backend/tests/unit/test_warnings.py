"""T20: advertencias de saldo (RF-14, plan §3.4). Avisan, nunca bloquean."""

import uuid
from dataclasses import replace

from finanzas.domain import messages
from finanzas.domain.accounts import AccountType
from finanzas.domain.balances import AccountInfo, BalanceWarning, detect_warnings

NEQUI = AccountInfo(uuid.uuid4(), "Nequi Prueba", AccountType.DIGITAL_WALLET, None, 0)
CASH = AccountInfo(uuid.uuid4(), "Efectivo Prueba", AccountType.CASH, None, 0)


def test_positive_or_zero_balances_produce_no_warnings() -> None:
    assert detect_warnings([NEQUI, CASH], {NEQUI.id: 0, CASH.id: 500}) == []


def test_negative_balance_warns_with_account_and_balance() -> None:
    warnings = detect_warnings([NEQUI], {NEQUI.id: -72850000})
    assert warnings == [
        BalanceWarning(
            code="negative_balance",
            account_id=NEQUI.id,
            account_name="Nequi Prueba",
            balance_cents=-72850000,
            message=messages.render("negative_balance", account="Nequi Prueba"),
        )
    ]
    assert "Nequi Prueba" in warnings[0].message


def test_archived_account_with_nonzero_balance_warns() -> None:
    archived = replace(CASH, archived=True)
    warnings = detect_warnings([archived], {CASH.id: 700000})
    assert [(w.code, w.balance_cents) for w in warnings] == [
        ("archived_nonzero_balance", 700000)
    ]


def test_archived_account_in_negative_gets_both_warnings() -> None:
    archived = replace(CASH, archived=True)
    codes = [w.code for w in detect_warnings([archived], {CASH.id: -1})]
    assert codes == ["negative_balance", "archived_nonzero_balance"]


def test_archived_account_at_zero_does_not_warn() -> None:
    assert detect_warnings([replace(CASH, archived=True)], {CASH.id: 0}) == []


def test_each_affected_account_is_checked_once_in_order() -> None:
    warnings = detect_warnings([NEQUI, CASH, NEQUI], {NEQUI.id: -1, CASH.id: -2})
    assert [w.account_name for w in warnings] == ["Nequi Prueba", "Efectivo Prueba"]
