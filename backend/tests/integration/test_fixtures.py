"""T15: los «moldes» de datos sintéticos funcionan (RNF-5, RNF-6, plan §8.2)."""

from collections.abc import Callable
from datetime import date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, MovementVersion, User
from finanzas.domain.accounts import AccountType
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import BOGOTA, FixedClock
from finanzas.domain.movements import AdjustmentDirection, MovementType


def test_clock_is_fixed_on_the_reference_day(clock: FixedClock) -> None:
    assert clock.now() == datetime(2026, 11, 23, 10, 0, tzinfo=BOGOTA)
    assert clock.today() == date(2026, 11, 23)


def test_two_distinct_owners_exist(
    db_session: Session, owner_a: User, owner_b: User
) -> None:
    assert owner_a.id != owner_b.id
    ids = set(db_session.scalars(select(User.id)))
    assert {owner_a.id, owner_b.id} <= ids


def test_make_account_belongs_to_owner_with_invented_name(
    owner_a: User, make_account: Callable[..., Account]
) -> None:
    first, second = make_account(owner_a), make_account(owner_a)
    assert first.owner_id == owner_a.id
    assert first.name != second.name  # se pueden crear varias sin chocar
    assert "Prueba" in first.name
    assert first.start_date == date(2026, 11, 1)


def test_make_account_can_create_a_pocket(
    owner_a: User, make_account: Callable[..., Account]
) -> None:
    bank = make_account(owner_a, initial_balance_cents=150000000)
    pocket = make_account(owner_a, AccountType.POCKET, parent=bank)
    assert pocket.parent_id == bank.id
    assert bank.initial_balance_cents == 150000000


def test_make_category_defaults_to_expense(
    owner_b: User, make_category: Callable[..., Category]
) -> None:
    expense = make_category(owner_b)
    income = make_category(owner_b, CategoryKind.INCOME)
    assert (expense.kind, income.kind) == (CategoryKind.EXPENSE, CategoryKind.INCOME)
    assert expense.owner_id == owner_b.id
    assert "Prueba" in expense.name


def test_make_movement_creates_expense_with_its_first_version(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_movement: Callable[..., Movement],
) -> None:
    movement = make_movement(owner_a)
    assert movement.type is MovementType.EXPENSE
    assert movement.owner_id == owner_a.id
    assert movement.date == clock.today()
    assert movement.created_at == clock.now()
    assert movement.current_version == 1
    versions = db_session.scalars(
        select(MovementVersion).where(MovementVersion.movement_id == movement.id)
    ).all()
    assert [(v.version_no, v.changed_fields) for v in versions] == [(1, [])]
    assert versions[0].amount_cents == movement.amount_cents


@pytest.mark.parametrize(
    ("movement_type", "direction"),
    [
        (MovementType.INCOME, None),
        (MovementType.TRANSFER, None),
        (MovementType.YIELD, None),
        (MovementType.ADJUSTMENT, AdjustmentDirection.IN),
        (MovementType.ADJUSTMENT, AdjustmentDirection.OUT),
    ],
)
def test_make_movement_builds_every_valid_shape(
    owner_b: User,
    make_movement: Callable[..., Movement],
    movement_type: MovementType,
    direction: AdjustmentDirection | None,
) -> None:
    movement = make_movement(
        owner_b, movement_type, adjustment_direction=direction, amount_cents=123456
    )
    assert movement.type is movement_type
    assert movement.amount_cents == 123456


def test_make_movement_uses_given_accounts_and_category(
    owner_a: User,
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_movement: Callable[..., Movement],
) -> None:
    bank, cash = make_account(owner_a), make_account(owner_a, AccountType.CASH)
    category = make_category(owner_a)
    expense = make_movement(owner_a, from_account=bank, category=category)
    transfer = make_movement(
        owner_a, MovementType.TRANSFER, from_account=bank, to_account=cash
    )
    assert (expense.from_account_id, expense.category_id) == (bank.id, category.id)
    assert (transfer.from_account_id, transfer.to_account_id) == (bank.id, cash.id)
