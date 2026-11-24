"""T38: historial de un movimiento (RF-20, RNF-2, plan §3.6)."""

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, MovementVersion, User
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.errors import NotFound
from finanzas.domain.movements import MovementType
from finanzas.services import categories as categories_service
from finanzas.services import movements as service


@pytest.fixture
def food(owner_a: User, make_category: Callable[..., Category]) -> Category:
    return make_category(owner_a, CategoryKind.EXPENSE, name="Comida")


@pytest.fixture
def expense(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    food: Category,
    make_account: Callable[..., Account],
) -> Movement:
    bank = make_account(owner_a, name="Nequi Prueba")
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


def test_versions_come_in_order_with_what_changed(
    db_session: Session, clock: FixedClock, owner_a: User, expense: Movement
) -> None:
    first_at = clock.now()
    clock.advance(timedelta(hours=6))
    service.correct_movement(
        db_session, owner_a.id, clock, expense.id, amount_cents=2500000
    )
    second_at = clock.now()
    clock.advance(timedelta(days=1))
    service.correct_movement(db_session, owner_a.id, clock, expense.id, note="Cena")

    history = service.get_history(db_session, owner_a.id, expense.id)

    assert history.movement_id == expense.id
    assert [
        (v.version, v.created_at, v.changed_fields, v.amount_cents, v.note)
        for v in history.versions
    ] == [
        (1, first_at, [], 2300000, "Almuerzo"),
        (2, second_at, ["amount_cents"], 2500000, "Almuerzo"),
        (3, clock.now(), ["note"], 2500000, "Cena"),
    ]
    first = history.versions[0]
    assert (first.date, first.merchant) == (date(2026, 11, 3), "rappi")
    assert first.from_account is not None
    assert first.from_account.name == "Nequi Prueba"
    assert first.to_account is None
    assert history.voided is None


def test_void_appears_at_the_end_with_its_reason(
    db_session: Session, clock: FixedClock, owner_a: User, expense: Movement
) -> None:
    clock.advance(timedelta(hours=1))
    service.void_movement(
        db_session, owner_a.id, clock, expense.id, reason="Registrado dos veces"
    )
    history = service.get_history(db_session, owner_a.id, expense.id)
    assert history.voided is not None
    assert (history.voided.at, history.voided.reason) == (
        clock.now(),
        "Registrado dos veces",
    )


def test_renamed_category_shows_its_current_name_in_old_versions(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    food: Category,
    expense: Movement,
) -> None:
    categories_service.rename_category(
        db_session, owner_a.id, food.id, name="Alimentación"
    )
    history = service.get_history(db_session, owner_a.id, expense.id)
    assert history.versions[0].category is not None
    assert (history.versions[0].category.id, history.versions[0].category.name) == (
        food.id,
        "Alimentación",
    )


def test_no_operation_deletes_versions(
    db_session: Session, clock: FixedClock, owner_a: User, expense: Movement
) -> None:
    def count() -> int:
        return (
            db_session.scalar(
                select(func.count())
                .select_from(MovementVersion)
                .where(MovementVersion.movement_id == expense.id)
            )
            or 0
        )

    seen = [count()]
    service.correct_movement(db_session, owner_a.id, clock, expense.id, amount_cents=1)
    seen.append(count())
    service.correct_movement(
        db_session, owner_a.id, clock, expense.id, merchant="RAPPI"
    )
    seen.append(count())  # sin cambio real: no agrega, tampoco borra
    service.void_movement(db_session, owner_a.id, clock, expense.id)
    seen.append(count())
    assert seen == [1, 2, 2, 2]
    assert not any(name.startswith("delete") for name in dir(service))


def test_history_of_another_users_movement_looks_like_it_does_not_exist(
    db_session: Session, owner_b: User, expense: Movement
) -> None:
    with pytest.raises(NotFound) as caught:
        service.get_history(db_session, owner_b.id, expense.id)
    assert (caught.value.code, caught.value.field) == (
        "resource_not_found",
        "movement_id",
    )
