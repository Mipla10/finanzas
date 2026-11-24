"""T30–T32: registrar movimientos (RF-2, RF-7 a RF-11, RF-14, plan §3.5)."""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, MovementVersion, User
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.errors import Conflict, DomainError, InvalidData, NotFound
from finanzas.domain.movements import MovementType
from finanzas.services import movements as service

EXPENSE, INCOME = MovementType.EXPENSE, MovementType.INCOME


def expect(
    error: type[DomainError], code: str, field: str | None, call: Callable[[], Any]
) -> None:
    with pytest.raises(error) as caught:
        call()
    assert (caught.value.code, caught.value.field) == (code, field)


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


@pytest.fixture
def bank(owner_a: User, make_account: Callable[..., Account]) -> Account:
    return make_account(owner_a, name="Banco Prueba", initial_balance_cents=10_000_000)


@pytest.fixture
def food(owner_a: User, make_category: Callable[..., Category]) -> Category:
    return make_category(owner_a, CategoryKind.EXPENSE, name="Comida Prueba")


@pytest.fixture
def salary(owner_a: User, make_category: Callable[..., Category]) -> Category:
    return make_category(owner_a, CategoryKind.INCOME, name="Salario Prueba")


def spend(session: Session, owner: User, clock: FixedClock, **fields: Any) -> Movement:
    return service.create_movement(
        session, owner.id, clock, movement_type=EXPENSE, **fields
    )


# --- T30: gasto e ingreso ---


def test_expense_is_stored_with_its_first_version(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    food: Category,
) -> None:
    movement = spend(
        db_session,
        owner_a,
        clock,
        amount_cents=2500000,
        on=date(2026, 11, 3),
        from_account_id=bank.id,
        category_id=food.id,
        merchant="  rappi ",
        note="  Almuerzo  ",
    )
    assert movement.owner_id == owner_a.id
    assert (movement.type, movement.amount_cents, movement.date) == (
        EXPENSE,
        2500000,
        date(2026, 11, 3),
    )
    assert (movement.from_account_id, movement.to_account_id) == (bank.id, None)
    assert (movement.merchant, movement.merchant_key, movement.note) == (
        "rappi",
        "rappi",
        "Almuerzo",
    )
    assert movement.created_at == movement.updated_at == clock.now()
    assert (movement.current_version, movement.voided_at) == (1, None)
    versions = db_session.scalars(
        select(MovementVersion).where(MovementVersion.movement_id == movement.id)
    ).all()
    assert [(v.version_no, v.changed_fields, v.amount_cents) for v in versions] == [
        (1, [], 2500000)
    ]
    assert versions[0].created_at == clock.now()


def test_income_is_stored(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    salary: Category,
) -> None:
    movement = service.create_movement(
        db_session,
        owner_a.id,
        clock,
        movement_type=INCOME,
        amount_cents=200000000,
        to_account_id=bank.id,
        category_id=salary.id,
    )
    assert (movement.type, movement.to_account_id, movement.from_account_id) == (
        INCOME,
        bank.id,
        None,
    )
    assert (movement.merchant, movement.note) == (None, None)


def test_without_date_it_is_today(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    food: Category,
) -> None:
    movement = spend(
        db_session,
        owner_a,
        clock,
        amount_cents=1,
        from_account_id=bank.id,
        category_id=food.id,
    )
    assert movement.date == clock.today()


def test_cl_6_tomorrow_is_rejected(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    food: Category,
) -> None:
    expect(
        InvalidData,
        "date_in_future",
        "date",
        lambda: spend(
            db_session,
            owner_a,
            clock,
            amount_cents=1,
            from_account_id=bank.id,
            category_id=food.id,
            on=clock.today() + timedelta(days=1),
        ),
    )


def test_cl_8_and_cl_9_start_day_accepted_day_before_rejected(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    food: Category,
) -> None:
    ok = spend(
        db_session,
        owner_a,
        clock,
        amount_cents=1,
        from_account_id=bank.id,
        category_id=food.id,
        on=bank.start_date,
    )
    assert ok.date == bank.start_date
    expect(
        InvalidData,
        "date_before_account_start",
        "date",
        lambda: spend(
            db_session,
            owner_a,
            clock,
            amount_cents=1,
            from_account_id=bank.id,
            category_id=food.id,
            on=bank.start_date - timedelta(days=1),
        ),
    )


def test_archived_account_is_a_conflict(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    food: Category,
) -> None:
    bank.archived_at = clock.now()
    db_session.flush()
    expect(
        Conflict,
        "account_archived",
        "from_account_id",
        lambda: spend(
            db_session,
            owner_a,
            clock,
            amount_cents=1,
            from_account_id=bank.id,
            category_id=food.id,
        ),
    )


def test_archived_category_is_a_conflict(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    food: Category,
) -> None:
    food.archived_at = clock.now()
    db_session.flush()
    expect(
        Conflict,
        "category_archived",
        "category_id",
        lambda: spend(
            db_session,
            owner_a,
            clock,
            amount_cents=1,
            from_account_id=bank.id,
            category_id=food.id,
        ),
    )


def test_category_of_the_wrong_kind_is_rejected(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    salary: Category,
) -> None:
    expect(
        InvalidData,
        "category_wrong_kind",
        "category_id",
        lambda: spend(
            db_session,
            owner_a,
            clock,
            amount_cents=1,
            from_account_id=bank.id,
            category_id=salary.id,
        ),
    )


def test_adjustments_are_not_created_here(
    db_session: Session, clock: FixedClock, owner_a: User, bank: Account
) -> None:
    expect(
        InvalidData,
        "adjustment_not_via_movements",
        "type",
        lambda: service.create_movement(
            db_session,
            owner_a.id,
            clock,
            movement_type=MovementType.ADJUSTMENT,
            amount_cents=1,
            to_account_id=bank.id,
        ),
    )


@pytest.mark.parametrize(
    ("fields", "error", "code", "field"),
    [
        ({"amount_cents": 0}, InvalidData, "amount_not_positive", "amount_cents"),
        ({"category_id": None}, InvalidData, "required", "category_id"),
        ({"merchant": "m" * 81}, InvalidData, "too_long", "merchant"),
    ],
)
def test_invalid_data_saves_nothing(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    food: Category,
    fields: dict[str, Any],
    error: type[DomainError],
    code: str,
    field: str,
) -> None:
    values = {"amount_cents": 1, "from_account_id": bank.id, "category_id": food.id}
    values.update(fields)
    expect(error, code, field, lambda: spend(db_session, owner_a, clock, **values))
    assert count(db_session, Movement) == count(db_session, MovementVersion) == 0


@pytest.mark.parametrize("borrowed", ["from_account_id", "category_id"])
def test_resources_of_another_user_look_like_they_do_not_exist(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    owner_b: User,
    bank: Account,
    food: Category,
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    borrowed: str,
) -> None:
    values = {"amount_cents": 1, "from_account_id": bank.id, "category_id": food.id}
    values[borrowed] = (
        make_account(owner_b).id
        if borrowed == "from_account_id"
        else make_category(owner_b).id
    )
    expect(
        NotFound,
        "resource_not_found",
        borrowed,
        lambda: spend(db_session, owner_a, clock, **values),
    )
