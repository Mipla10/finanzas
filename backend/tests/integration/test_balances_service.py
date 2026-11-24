"""T42: saldos por cuenta, subtotal banco + bolsillos y total (RF-15, RF-16, CL-4).

Carga en la BD real el ejemplo de plan §2.4 y exige sus valores exactos.
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from finanzas.db.models import Account, User
from finanzas.domain.dates import FixedClock
from finanzas.services import balances as service


def test_plan_example_gives_the_exact_hand_calculated_values(
    db_session: Session, owner_a: User, month_scenario: dict[str, Account]
) -> None:
    accounts = month_scenario

    summary = service.get_balances(db_session, owner_a.id)

    assert [(a.name, a.balance_cents, a.archived) for a in summary.accounts] == [
        ("Lulo", 279300000, False),
        ("Ahorro", 351234567, False),
        ("Nequi", 17150000, False),
        ("Efectivo", 25000000, False),
    ]
    assert summary.accounts[1].parent_id == accounts["Lulo"].id
    assert [(g.bank_id, g.name, g.subtotal_cents) for g in summary.groups] == [
        (accounts["Lulo"].id, "Lulo", 630534567)
    ]
    assert summary.total_cents == 672684567


def test_archived_accounts_hidden_at_zero_shown_marked_otherwise(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
) -> None:
    at_zero = make_account(owner_a, name="Vieja Prueba", initial_balance_cents=0)
    with_money = make_account(
        owner_a, name="Olvidada Prueba", initial_balance_cents=700
    )
    active = make_account(owner_a, name="Activa Prueba", initial_balance_cents=300)
    at_zero.archived_at = with_money.archived_at = clock.now()
    db_session.flush()

    summary = service.get_balances(db_session, owner_a.id)

    shown = {a.account_id: a.archived for a in summary.accounts}
    assert shown == {with_money.id: True, active.id: False}
    assert summary.total_cents == 1000  # la de 0 no suma nada, pero cuenta


def test_only_my_accounts_and_empty_when_i_have_none(
    db_session: Session,
    owner_a: User,
    owner_b: User,
    make_account: Callable[..., Account],
) -> None:
    empty = service.get_balances(db_session, owner_a.id)
    assert (empty.accounts, empty.groups, empty.total_cents) == ([], [], 0)
    make_account(owner_b, initial_balance_cents=999)
    assert service.get_balances(db_session, owner_a.id).total_cents == 0
