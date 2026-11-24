"""T37: anular un movimiento (RF-21, CL-25, CL-26, CL-27, plan §3.7)."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, User
from finanzas.db.repositories.balances import balances_for_owner
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.errors import Conflict, DomainError, InvalidData, NotFound
from finanzas.domain.movements import MovementType
from finanzas.services import movements as service


def expect(
    error: type[DomainError], code: str, field: str | None, call: Callable[[], Any]
) -> None:
    with pytest.raises(error) as caught:
        call()
    assert (caught.value.code, caught.value.field) == (code, field)


def balance(session: Session, owner: User, account: Account) -> int:
    return balances_for_owner(session, owner.id, [account.id])[account.id]


@pytest.fixture
def cash(owner_a: User, make_account: Callable[..., Account]) -> Account:
    return make_account(owner_a, name="Efectivo Prueba", initial_balance_cents=0)


@pytest.fixture
def salary(owner_a: User, make_category: Callable[..., Category]) -> Category:
    return make_category(owner_a, CategoryKind.INCOME, name="Salario Prueba")


def earn(
    session: Session,
    owner: User,
    clock: FixedClock,
    account: Account,
    category: Category,
    amount: int,
) -> Movement:
    return service.create_movement(
        session,
        owner.id,
        clock,
        movement_type=MovementType.INCOME,
        amount_cents=amount,
        to_account_id=account.id,
        category_id=category.id,
    ).movement


def test_void_records_moment_and_reason_and_stops_counting(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    cash: Account,
    salary: Category,
) -> None:
    income = earn(db_session, owner_a, clock, cash, salary, 5000)
    assert balance(db_session, owner_a, cash) == 5000
    clock.advance(timedelta(hours=1))

    result = service.void_movement(
        db_session, owner_a.id, clock, income.id, reason="  Registrado dos veces  "
    )

    assert result.movement.voided_at == clock.now()
    assert result.movement.void_reason == "Registrado dos veces"
    assert balance(db_session, owner_a, cash) == 0  # ya no cuenta
    assert result.movement.amount_cents == 5000  # sigue siendo consultable
    assert result.movement.current_version == 1  # anular no crea versión


def test_reason_is_optional(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    cash: Account,
    salary: Category,
) -> None:
    income = earn(db_session, owner_a, clock, cash, salary, 1)
    voided = service.void_movement(db_session, owner_a.id, clock, income.id).movement
    assert (voided.voided_at, voided.void_reason) == (clock.now(), None)


def test_too_long_reason_is_rejected(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    cash: Account,
    salary: Category,
) -> None:
    income = earn(db_session, owner_a, clock, cash, salary, 1)
    expect(
        InvalidData,
        "too_long",
        "reason",
        lambda: service.void_movement(
            db_session, owner_a.id, clock, income.id, reason="r" * 201
        ),
    )
    assert income.voided_at is None


def test_cl_25_voiding_twice_is_a_conflict(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    cash: Account,
    salary: Category,
) -> None:
    income = earn(db_session, owner_a, clock, cash, salary, 1)
    service.void_movement(db_session, owner_a.id, clock, income.id)
    expect(
        Conflict,
        "already_voided",
        None,
        lambda: service.void_movement(db_session, owner_a.id, clock, income.id),
    )


def test_cl_26_voiding_an_income_into_negative_warns(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    cash: Account,
    salary: Category,
    make_movement: Callable[..., Any],
) -> None:
    income = earn(db_session, owner_a, clock, cash, salary, 5000)
    make_movement(owner_a, from_account=cash, amount_cents=3000)  # saldo 2000
    result = service.void_movement(db_session, owner_a.id, clock, income.id)
    assert [(w.code, w.balance_cents) for w in result.warnings] == [
        ("negative_balance", -3000)
    ]


def test_cl_27_voiding_in_an_archived_account_is_allowed_and_warns(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    cash: Account,
    salary: Category,
) -> None:
    income = earn(db_session, owner_a, clock, cash, salary, 5000)
    cash.initial_balance_cents = -5000  # saldo 0 para poder archivarla
    cash.archived_at = clock.now()
    db_session.flush()
    result = service.void_movement(db_session, owner_a.id, clock, income.id)
    assert [w.code for w in result.warnings] == [
        "negative_balance",
        "archived_nonzero_balance",
    ]


def test_an_adjustment_can_be_voided(
    db_session: Session, clock: FixedClock, owner_a: User, cash: Account
) -> None:
    from finanzas.services.adjustments import adjust_balance

    adjustment = adjust_balance(
        db_session, owner_a.id, clock, cash.id, real_balance_cents=700
    ).movement
    assert adjustment is not None
    service.void_movement(db_session, owner_a.id, clock, adjustment.id)
    assert balance(db_session, owner_a, cash) == 0


def test_voiding_another_users_movement_looks_like_it_does_not_exist(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    owner_b: User,
    cash: Account,
    salary: Category,
) -> None:
    income = earn(db_session, owner_a, clock, cash, salary, 1)
    expect(
        NotFound,
        "resource_not_found",
        "movement_id",
        lambda: service.void_movement(db_session, owner_b.id, clock, income.id),
    )
    assert income.voided_at is None
