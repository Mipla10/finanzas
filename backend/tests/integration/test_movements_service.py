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
    ).movement


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
    ).movement
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


# --- T31: transferencias y rendimientos (RF-10, RF-11, CL-3, CL-4, CL-5, CL-12) ---

TRANSFER, YIELD = MovementType.TRANSFER, MovementType.YIELD


def balances(session: Session, owner: User) -> dict[Any, int]:
    from finanzas.db.repositories.balances import balances_for_owner

    return balances_for_owner(session, owner.id)


def test_cl_3_atm_withdrawal_with_fee(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> None:
    cash = make_account(owner_a, name="Efectivo Prueba", initial_balance_cents=0)
    fees = make_category(owner_a, CategoryKind.EXPENSE, name="Comisiones Prueba")
    before = balances(db_session, owner_a)

    service.create_movement(
        db_session,
        owner_a.id,
        clock,
        movement_type=TRANSFER,
        amount_cents=20000000,
        from_account_id=bank.id,
        to_account_id=cash.id,
    )
    spend(
        db_session,
        owner_a,
        clock,
        amount_cents=700000,
        from_account_id=bank.id,
        category_id=fees.id,
    )

    after = balances(db_session, owner_a)
    assert before[bank.id] - after[bank.id] == 20700000
    assert after[cash.id] - before[cash.id] == 20000000
    expenses = db_session.scalars(
        select(Movement.amount_cents).where(Movement.type == EXPENSE)
    ).all()
    assert expenses == [700000]  # solo la comisión es gasto


def test_cl_4_transfer_between_pockets_keeps_bank_subtotal(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
) -> None:
    from finanzas.domain.accounts import AccountType

    lulo = make_account(owner_a, name="Lulo Prueba", initial_balance_cents=100)
    ahorro = make_account(
        owner_a,
        AccountType.POCKET,
        name="Ahorro Prueba",
        parent=lulo,
        initial_balance_cents=5000,
    )
    viajes = make_account(
        owner_a,
        AccountType.POCKET,
        name="Viajes Prueba",
        parent=lulo,
        initial_balance_cents=0,
    )

    def subtotal() -> int:
        current = balances(db_session, owner_a)
        return current[lulo.id] + current[ahorro.id] + current[viajes.id]

    before = subtotal()
    service.create_movement(
        db_session,
        owner_a.id,
        clock,
        movement_type=TRANSFER,
        amount_cents=3000,
        from_account_id=ahorro.id,
        to_account_id=viajes.id,
    )
    assert subtotal() == before
    assert balances(db_session, owner_a)[viajes.id] == 3000


def test_cl_5_transfer_to_the_same_account_is_rejected(
    db_session: Session, clock: FixedClock, owner_a: User, bank: Account
) -> None:
    expect(
        InvalidData,
        "same_account",
        "to_account_id",
        lambda: service.create_movement(
            db_session,
            owner_a.id,
            clock,
            movement_type=TRANSFER,
            amount_cents=1,
            from_account_id=bank.id,
            to_account_id=bank.id,
        ),
    )


def test_cl_12_yield_with_cents_adds_exactly(
    db_session: Session, clock: FixedClock, owner_a: User, bank: Account
) -> None:
    before = balances(db_session, owner_a)[bank.id]
    movement = service.create_movement(
        db_session,
        owner_a.id,
        clock,
        movement_type=YIELD,
        amount_cents=123456,
        to_account_id=bank.id,
    ).movement
    assert (movement.category_id, movement.from_account_id) == (None, None)
    assert balances(db_session, owner_a)[bank.id] - before == 123456


@pytest.mark.parametrize("movement_type", [TRANSFER, YIELD])
def test_transfer_and_yield_reject_a_category(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    food: Category,
    make_account: Callable[..., Account],
    movement_type: MovementType,
) -> None:
    to_account = make_account(owner_a)
    from_account = bank.id if movement_type is TRANSFER else None
    expect(
        InvalidData,
        "not_allowed_for_type",
        "category_id",
        lambda: service.create_movement(
            db_session,
            owner_a.id,
            clock,
            movement_type=movement_type,
            amount_cents=1,
            from_account_id=from_account,
            to_account_id=to_account.id,
            category_id=food.id,
        ),
    )


def test_destination_account_is_checked_too(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    owner_b: User,
    bank: Account,
    make_account: Callable[..., Account],
) -> None:
    archived = make_account(owner_a, name="Archivada Prueba")
    archived.archived_at = clock.now()
    late = make_account(owner_a, name="Tardía Prueba", start_date=date(2026, 11, 20))
    theirs = make_account(owner_b)
    db_session.flush()

    def transfer(to_id: Any, on: date | None = None) -> Movement:
        return service.create_movement(
            db_session,
            owner_a.id,
            clock,
            movement_type=TRANSFER,
            amount_cents=1,
            from_account_id=bank.id,
            to_account_id=to_id,
            on=on,
        ).movement

    expect(Conflict, "account_archived", "to_account_id", lambda: transfer(archived.id))
    expect(NotFound, "resource_not_found", "to_account_id", lambda: transfer(theirs.id))
    expect(
        InvalidData,
        "date_before_account_start",
        "date",
        lambda: transfer(late.id, on=date(2026, 11, 10)),
    )


# --- T32: advertencias al crear (RF-14, CL-1, CL-2) ---


def test_creating_returns_the_movement_and_no_warnings_when_all_is_fine(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    food: Category,
) -> None:
    result = service.create_movement(
        db_session,
        owner_a.id,
        clock,
        movement_type=EXPENSE,
        amount_cents=1,
        from_account_id=bank.id,
        category_id=food.id,
    )
    assert result.movement.amount_cents == 1
    assert result.warnings == []


def test_cl_1_expense_into_negative_is_saved_with_a_warning(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    food: Category,
    make_account: Callable[..., Account],
) -> None:
    nequi = make_account(owner_a, name="Nequi Prueba", initial_balance_cents=1000)
    result = service.create_movement(
        db_session,
        owner_a.id,
        clock,
        movement_type=EXPENSE,
        amount_cents=6000,
        from_account_id=nequi.id,
        category_id=food.id,
    )
    assert count(db_session, Movement) == 1  # se guardó: avisa, no bloquea
    assert [
        (w.code, w.account_id, w.account_name, w.balance_cents) for w in result.warnings
    ] == [("negative_balance", nequi.id, "Nequi Prueba", -5000)]
    assert "Nequi Prueba" in result.warnings[0].message


def test_cl_2_expense_before_same_day_income(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    food: Category,
    salary: Category,
    make_account: Callable[..., Account],
) -> None:
    nequi = make_account(owner_a, name="Nequi Prueba", initial_balance_cents=0)
    expense = service.create_movement(
        db_session,
        owner_a.id,
        clock,
        movement_type=EXPENSE,
        amount_cents=5000,
        from_account_id=nequi.id,
        category_id=food.id,
    )
    assert [w.balance_cents for w in expense.warnings] == [-5000]
    income = service.create_movement(
        db_session,
        owner_a.id,
        clock,
        movement_type=INCOME,
        amount_cents=5000,
        to_account_id=nequi.id,
        category_id=salary.id,
    )
    assert income.warnings == []  # ya volvió a 0: sin aviso


def test_transfer_checks_both_accounts(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
) -> None:
    origin = make_account(owner_a, name="Origen Prueba", initial_balance_cents=0)
    destination = make_account(
        owner_a, name="Destino Prueba", initial_balance_cents=-10000
    )
    result = service.create_movement(
        db_session,
        owner_a.id,
        clock,
        movement_type=TRANSFER,
        amount_cents=1000,
        from_account_id=origin.id,
        to_account_id=destination.id,
    )
    assert [(w.account_name, w.balance_cents) for w in result.warnings] == [
        ("Origen Prueba", -1000),
        ("Destino Prueba", -9000),
    ]
