"""T33: ajuste de saldo al valor real del banco (RF-12, CL-14 a CL-16, plan §3.3)."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Movement, MovementVersion, User
from finanzas.db.repositories.balances import balances_for_owner
from finanzas.domain.accounts import AccountType
from finanzas.domain.dates import FixedClock
from finanzas.domain.errors import Conflict, DomainError, InvalidData, NotFound
from finanzas.domain.movements import AdjustmentDirection, MovementType
from finanzas.services import adjustments as service


def expect(
    error: type[DomainError], code: str, field: str | None, call: Callable[[], Any]
) -> None:
    with pytest.raises(error) as caught:
        call()
    assert (caught.value.code, caught.value.field) == (code, field)


def movements_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Movement)) or 0


def balance(session: Session, owner: User, account: Account) -> int:
    return balances_for_owner(session, owner.id, [account.id])[account.id]


def test_cl_14_already_balanced_creates_nothing(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
) -> None:
    nequi = make_account(owner_a, initial_balance_cents=17150000)
    result = service.adjust_balance(
        db_session, owner_a.id, clock, nequi.id, real_balance_cents=17150000
    )
    assert (result.status, result.movement, result.balance_cents) == (
        "already_balanced",
        None,
        17150000,
    )
    assert result.warnings == []
    assert movements_count(db_session) == 0


def test_plan_example_m8_money_out(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
    make_movement: Callable[..., Any],
) -> None:
    nequi = make_account(owner_a, initial_balance_cents=20000000)
    make_movement(owner_a, from_account=nequi, amount_cents=2500000)  # saldo 17500000

    result = service.adjust_balance(
        db_session, owner_a.id, clock, nequi.id, real_balance_cents=17150000
    )

    movement = result.movement
    assert result.status == "adjusted"
    assert movement is not None
    assert (movement.type, movement.adjustment_direction, movement.amount_cents) == (
        MovementType.ADJUSTMENT,
        AdjustmentDirection.OUT,
        350000,
    )
    assert (movement.from_account_id, movement.to_account_id) == (nequi.id, None)
    assert (movement.date, movement.category_id) == (clock.today(), None)
    assert movement.created_at == clock.now()
    assert result.balance_cents == balance(db_session, owner_a, nequi) == 17150000
    versions = db_session.scalars(
        select(MovementVersion.version_no).where(
            MovementVersion.movement_id == movement.id
        )
    ).all()
    assert versions == [1]


def test_money_in_when_bank_shows_more(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
) -> None:
    cash = make_account(owner_a, AccountType.CASH, initial_balance_cents=1000)
    movement = service.adjust_balance(
        db_session, owner_a.id, clock, cash.id, real_balance_cents=1500
    ).movement
    assert movement is not None
    assert (movement.adjustment_direction, movement.amount_cents) == (
        AdjustmentDirection.IN,
        500,
    )
    assert (movement.from_account_id, movement.to_account_id) == (None, cash.id)


def test_cl_15_bank_adjustment_ignores_its_pockets(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
) -> None:
    lulo = make_account(owner_a, name="Lulo Prueba", initial_balance_cents=1000)
    ahorro = make_account(
        owner_a,
        AccountType.POCKET,
        name="Ahorro Prueba",
        parent=lulo,
        initial_balance_cents=50000,
    )
    result = service.adjust_balance(
        db_session, owner_a.id, clock, lulo.id, real_balance_cents=1000
    )
    assert result.status == "already_balanced"  # no compara con 51000
    assert balance(db_session, owner_a, ahorro) == 50000


def test_cl_16_negative_real_balance_warns(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
) -> None:
    cash = make_account(owner_a, name="Efectivo Prueba", initial_balance_cents=0)
    result = service.adjust_balance(
        db_session, owner_a.id, clock, cash.id, real_balance_cents=-500000
    )
    assert result.movement is not None
    assert (result.movement.adjustment_direction, result.movement.amount_cents) == (
        AdjustmentDirection.OUT,
        500000,
    )
    assert [(w.code, w.balance_cents) for w in result.warnings] == [
        ("negative_balance", -500000)
    ]


def test_second_adjustment_same_day_starts_from_the_first(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
) -> None:
    cash = make_account(owner_a, initial_balance_cents=1000)
    first = service.adjust_balance(
        db_session, owner_a.id, clock, cash.id, real_balance_cents=500
    ).movement
    clock.advance(timedelta(hours=2))
    second = service.adjust_balance(
        db_session, owner_a.id, clock, cash.id, real_balance_cents=800
    ).movement
    assert first is not None and second is not None
    assert (first.adjustment_direction, first.amount_cents) == (
        AdjustmentDirection.OUT,
        500,
    )
    assert (second.adjustment_direction, second.amount_cents) == (
        AdjustmentDirection.IN,
        300,
    )
    assert first.date == second.date == clock.today()
    assert balance(db_session, owner_a, cash) == 800


def test_archived_account_is_a_conflict(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
) -> None:
    cash = make_account(owner_a)
    cash.archived_at = clock.now()
    db_session.flush()
    expect(
        Conflict,
        "account_archived",
        "account_id",
        lambda: service.adjust_balance(
            db_session, owner_a.id, clock, cash.id, real_balance_cents=1
        ),
    )


def test_invalid_real_balance_is_rejected(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
) -> None:
    cash = make_account(owner_a)
    expect(
        InvalidData,
        "amount_not_integer",
        "real_balance_cents",
        lambda: service.adjust_balance(
            db_session, owner_a.id, clock, cash.id, real_balance_cents=10.5
        ),
    )
    assert movements_count(db_session) == 0


def test_another_users_account_looks_like_it_does_not_exist(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    owner_b: User,
    make_account: Callable[..., Account],
) -> None:
    theirs = make_account(owner_b)
    expect(
        NotFound,
        "resource_not_found",
        "account_id",
        lambda: service.adjust_balance(
            db_session, owner_a.id, clock, theirs.id, real_balance_cents=0
        ),
    )
