"""T34–T35: corregir movimientos con historial (RF-19, RF-20, plan §3.6)."""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, MovementVersion, User
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


def versions(session: Session, movement: Movement) -> list[MovementVersion]:
    return list(
        session.scalars(
            select(MovementVersion)
            .where(MovementVersion.movement_id == movement.id)
            .order_by(MovementVersion.version_no)
        )
    )


@pytest.fixture
def bank(owner_a: User, make_account: Callable[..., Account]) -> Account:
    return make_account(owner_a, name="Banco Prueba", initial_balance_cents=10_000_000)


@pytest.fixture
def food(owner_a: User, make_category: Callable[..., Category]) -> Category:
    return make_category(owner_a, CategoryKind.EXPENSE, name="Comida Prueba")


@pytest.fixture
def expense(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    food: Category,
) -> Movement:
    """Plan §2.4, M2: se registró por 2300000 y luego se corrige a 2500000."""
    return service.create_movement(
        db_session,
        owner_a.id,
        clock,
        movement_type=MovementType.EXPENSE,
        amount_cents=2300000,
        on=date(2026, 11, 3),
        from_account_id=bank.id,
        category_id=food.id,
        merchant="rappi",
        note="Almuerzo",
    ).movement


# --- T34: corrección básica con versión ---


def test_correcting_the_amount_creates_version_2(
    db_session: Session, clock: FixedClock, owner_a: User, expense: Movement
) -> None:
    registered_at = expense.created_at
    clock.advance(timedelta(hours=6))

    result = service.correct_movement(
        db_session, owner_a.id, clock, expense.id, amount_cents=2500000
    )

    assert result.changed is True
    assert result.movement.id == expense.id  # sigue siendo el mismo movimiento
    assert (result.movement.amount_cents, result.movement.current_version) == (
        2500000,
        2,
    )
    assert result.movement.created_at == registered_at  # el orden no cambia
    assert result.movement.updated_at == clock.now()
    history = versions(db_session, expense)
    assert [(v.version_no, v.amount_cents, v.changed_fields) for v in history] == [
        (1, 2300000, []),
        (2, 2500000, ["amount_cents"]),
    ]
    assert history[1].created_at == clock.now()


def test_several_changes_are_recorded_in_a_stable_order(
    db_session: Session, clock: FixedClock, owner_a: User, expense: Movement
) -> None:
    result = service.correct_movement(
        db_session,
        owner_a.id,
        clock,
        expense.id,
        note="Cena",
        on=date(2026, 11, 4),
        merchant="Tienda Prueba",
    )
    assert versions(db_session, expense)[-1].changed_fields == [
        "date",
        "merchant",
        "note",
    ]
    assert (result.movement.merchant, result.movement.merchant_key) == (
        "Tienda Prueba",
        "tienda prueba",
    )


def test_removing_merchant_and_note_is_a_change(
    db_session: Session, clock: FixedClock, owner_a: User, expense: Movement
) -> None:
    result = service.correct_movement(
        db_session, owner_a.id, clock, expense.id, merchant=None, note="   "
    )
    assert (result.movement.merchant, result.movement.merchant_key) == (None, None)
    assert result.movement.note is None
    assert versions(db_session, expense)[-1].changed_fields == ["merchant", "note"]


def test_cl_19_changing_the_account_recalculates_both_and_warns(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    expense: Movement,
    make_account: Callable[..., Account],
) -> None:
    nequi = make_account(owner_a, name="Nequi Prueba", initial_balance_cents=1000)
    before = balances_for_owner(db_session, owner_a.id)

    result = service.correct_movement(
        db_session, owner_a.id, clock, expense.id, from_account_id=nequi.id
    )

    after = balances_for_owner(db_session, owner_a.id)
    assert after[bank.id] - before[bank.id] == 2300000  # el banco lo recupera
    assert after[nequi.id] == 1000 - 2300000  # Nequi lo paga
    assert [(w.account_name, w.balance_cents) for w in result.warnings] == [
        ("Nequi Prueba", 1000 - 2300000)
    ]
    assert versions(db_session, expense)[-1].changed_fields == ["from_account_id"]


def test_cl_24_only_case_of_the_merchant_is_not_a_change(
    db_session: Session, clock: FixedClock, owner_a: User, expense: Movement
) -> None:
    result = service.correct_movement(
        db_session, owner_a.id, clock, expense.id, merchant="  RAPPI "
    )
    assert result.changed is False
    assert result.warnings == []
    assert result.movement.merchant == "rappi"  # se conserva tal cual
    assert result.movement.current_version == 1
    assert len(versions(db_session, expense)) == 1


def test_nothing_given_is_not_a_change(
    db_session: Session, clock: FixedClock, owner_a: User, expense: Movement
) -> None:
    assert (
        service.correct_movement(db_session, owner_a.id, clock, expense.id).changed
        is False
    )


def test_correcting_another_users_movement_looks_like_it_does_not_exist(
    db_session: Session, clock: FixedClock, owner_b: User, expense: Movement
) -> None:
    expect(
        NotFound,
        "resource_not_found",
        "movement_id",
        lambda: service.correct_movement(
            db_session, owner_b.id, clock, expense.id, amount_cents=1
        ),
    )
    assert expense.amount_cents == 2300000


# --- T35: rechazos y cuentas o categorías archivadas (CL-18, CL-20 a CL-23, CL-25) ---


def test_cl_18_an_adjustment_cannot_be_corrected(
    db_session: Session, clock: FixedClock, owner_a: User, bank: Account
) -> None:
    from finanzas.services.adjustments import adjust_balance

    adjustment = adjust_balance(
        db_session, owner_a.id, clock, bank.id, real_balance_cents=1
    ).movement
    assert adjustment is not None
    expect(
        Conflict,
        "adjustment_not_correctable",
        None,
        lambda: service.correct_movement(
            db_session, owner_a.id, clock, adjustment.id, note="Otra"
        ),
    )


def test_cl_20_transfer_corrected_to_the_same_account_is_rejected(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    make_account: Callable[..., Account],
) -> None:
    cash = make_account(owner_a, name="Efectivo Prueba")
    transfer = service.create_movement(
        db_session,
        owner_a.id,
        clock,
        movement_type=MovementType.TRANSFER,
        amount_cents=1,
        from_account_id=bank.id,
        to_account_id=cash.id,
    ).movement
    expect(
        InvalidData,
        "same_account",
        "to_account_id",
        lambda: service.correct_movement(
            db_session, owner_a.id, clock, transfer.id, to_account_id=bank.id
        ),
    )


def test_cl_21_the_type_cannot_change(
    db_session: Session, clock: FixedClock, owner_a: User, expense: Movement
) -> None:
    expect(
        InvalidData,
        "type_not_changeable",
        "type",
        lambda: service.correct_movement(
            db_session,
            owner_a.id,
            clock,
            expense.id,
            movement_type=MovementType.TRANSFER,
        ),
    )
    # Repetir el mismo tipo no es un cambio.
    same = service.correct_movement(
        db_session, owner_a.id, clock, expense.id, movement_type=MovementType.EXPENSE
    )
    assert same.changed is False


def test_cl_22_note_of_an_expense_with_archived_category_can_be_corrected(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    food: Category,
    expense: Movement,
) -> None:
    food.archived_at = clock.now()
    db_session.flush()
    result = service.correct_movement(
        db_session, owner_a.id, clock, expense.id, note="Cena"
    )
    assert result.changed is True
    assert result.movement.category_id == food.id  # la conserva


def test_movement_of_an_archived_account_can_be_corrected(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    bank: Account,
    expense: Movement,
) -> None:
    bank.archived_at = clock.now()
    db_session.flush()
    result = service.correct_movement(
        db_session, owner_a.id, clock, expense.id, amount_cents=2500000
    )
    assert result.movement.from_account_id == bank.id
    assert result.movement.amount_cents == 2500000


def test_cl_23_choosing_an_archived_category_is_a_conflict(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    expense: Movement,
    make_category: Callable[..., Category],
) -> None:
    old = make_category(owner_a, CategoryKind.EXPENSE, name="Vieja Prueba")
    old.archived_at = clock.now()
    db_session.flush()
    expect(
        Conflict,
        "category_archived",
        "category_id",
        lambda: service.correct_movement(
            db_session, owner_a.id, clock, expense.id, category_id=old.id
        ),
    )


def test_choosing_an_archived_account_is_a_conflict(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    expense: Movement,
    make_account: Callable[..., Account],
) -> None:
    closed = make_account(owner_a, name="Cerrada Prueba")
    closed.archived_at = clock.now()
    db_session.flush()
    expect(
        Conflict,
        "account_archived",
        "from_account_id",
        lambda: service.correct_movement(
            db_session, owner_a.id, clock, expense.id, from_account_id=closed.id
        ),
    )


def test_cl_25_a_voided_movement_cannot_be_corrected(
    db_session: Session, clock: FixedClock, owner_a: User, expense: Movement
) -> None:
    expense.voided_at = clock.now()
    db_session.flush()
    expect(
        Conflict,
        "movement_voided",
        None,
        lambda: service.correct_movement(
            db_session, owner_a.id, clock, expense.id, amount_cents=1
        ),
    )
    assert expense.amount_cents == 2300000
