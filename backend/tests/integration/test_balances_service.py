"""T42: saldos por cuenta, subtotal banco + bolsillos y total (RF-15, RF-16, CL-4).

Carga en la BD real el ejemplo de plan §2.4 y exige sus valores exactos.
"""

from collections.abc import Callable
from datetime import date, timedelta

from sqlalchemy.orm import Session

from finanzas.db.models import Account, Movement, User
from finanzas.domain.accounts import AccountType
from finanzas.domain.dates import FixedClock
from finanzas.domain.movements import AdjustmentDirection, MovementType
from finanzas.services import balances as service

T = MovementType


def load_plan_example(
    session: Session,
    clock: FixedClock,
    owner: User,
    make_account: Callable[..., Account],
    make_movement: Callable[..., Movement],
) -> dict[str, Account]:
    accounts = {}
    for name, kind, parent, initial in [
        ("Lulo", AccountType.BANK, None, 150000000),
        ("Ahorro", AccountType.POCKET, "Lulo", 300000000),
        ("Nequi", AccountType.DIGITAL_WALLET, None, 20000000),
        ("Efectivo", AccountType.CASH, None, 5000000),
    ]:
        accounts[name] = make_account(
            owner,
            kind,
            name=name,
            parent=accounts.get(parent or ""),
            initial_balance_cents=initial,
        )
        clock.advance(timedelta(seconds=1))  # orden de creación estable
    lulo, ahorro, nequi, cash = (
        accounts[n] for n in ("Lulo", "Ahorro", "Nequi", "Efectivo")
    )

    def day(d: int) -> date:
        return date(2026, 11, d)

    make_movement(owner, T.INCOME, to_account=lulo, amount_cents=200000000, on=day(1))
    m2 = make_movement(owner, from_account=nequi, amount_cents=2300000, on=day(3))
    m2.amount_cents = 2500000  # M2 corregido (versión 2)
    make_movement(
        owner,
        T.TRANSFER,
        from_account=lulo,
        to_account=cash,
        amount_cents=20000000,
        on=day(5),
    )
    make_movement(owner, from_account=lulo, amount_cents=700000, on=day(5))
    make_movement(
        owner,
        T.TRANSFER,
        from_account=lulo,
        to_account=ahorro,
        amount_cents=50000000,
        on=day(6),
    )
    m6 = make_movement(owner, from_account=cash, amount_cents=8000000, on=day(10))
    m6.voided_at = clock.now()  # M6 anulado
    make_movement(owner, T.YIELD, to_account=ahorro, amount_cents=1234567, on=day(20))
    make_movement(
        owner,
        T.ADJUSTMENT,
        from_account=nequi,
        amount_cents=350000,
        adjustment_direction=AdjustmentDirection.OUT,
        on=day(23),
    )
    session.flush()
    return accounts


def test_plan_example_gives_the_exact_hand_calculated_values(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
    make_movement: Callable[..., Movement],
) -> None:
    accounts = load_plan_example(
        db_session, clock, owner_a, make_account, make_movement
    )

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
