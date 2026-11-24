"""T28/T29: casos de uso de categorías (RF-6, CL-31, CL-32)."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from finanzas.db.models import Category, User
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.errors import Conflict, DomainError, InvalidData, NotFound
from finanzas.services import categories as service

EXPENSE, INCOME = CategoryKind.EXPENSE, CategoryKind.INCOME


def create(
    session: Session,
    owner: User,
    clock: FixedClock,
    name: str,
    kind: CategoryKind = EXPENSE,
) -> Category:
    return service.create_category(session, owner.id, clock, name=name, kind=kind)


def expect(
    error: type[DomainError], code: str, field: str | None, call: Callable[[], Any]
) -> None:
    with pytest.raises(error) as caught:
        call()
    assert (caught.value.code, caught.value.field) == (code, field)


# --- T28: crear, listar y renombrar ---


def test_create_category(db_session: Session, clock: FixedClock, owner_a: User) -> None:
    category = create(db_session, owner_a, clock, "  Domicilios  ")
    assert (category.name, category.name_key, category.kind) == (
        "Domicilios",
        "domicilios",
        EXPENSE,
    )
    assert category.owner_id == owner_a.id
    assert category.created_at == clock.now()
    assert category.archived_at is None


def test_duplicate_name_in_same_kind_is_a_conflict(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    create(db_session, owner_a, clock, "Domicilios")
    expect(
        Conflict,
        "duplicate_category_name",
        "name",
        lambda: create(db_session, owner_a, clock, "DOMICILIOS"),
    )


def test_same_name_in_other_kind_or_other_user_is_fine(
    db_session: Session, clock: FixedClock, owner_a: User, owner_b: User
) -> None:
    create(db_session, owner_a, clock, "Otros", EXPENSE)
    assert create(db_session, owner_a, clock, "Otros", INCOME).kind is INCOME
    assert create(db_session, owner_b, clock, "Otros", EXPENSE).owner_id == owner_b.id


@pytest.mark.parametrize(
    ("name", "code"), [("   ", "required"), ("x" * 41, "too_long")]
)
def test_invalid_names_are_rejected(
    db_session: Session, clock: FixedClock, owner_a: User, name: str, code: str
) -> None:
    expect(InvalidData, code, "name", lambda: create(db_session, owner_a, clock, name))


def test_rename_category(db_session: Session, clock: FixedClock, owner_a: User) -> None:
    category = create(db_session, owner_a, clock, "Comida")
    renamed = service.rename_category(
        db_session, owner_a.id, category.id, name="Alimentación"
    )
    assert (renamed.name, renamed.name_key) == ("Alimentación", "alimentación")


def test_rename_to_an_existing_name_in_same_kind_is_a_conflict(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    create(db_session, owner_a, clock, "Ropa")
    category = create(db_session, owner_a, clock, "Vestuario")
    expect(
        Conflict,
        "duplicate_category_name",
        "name",
        lambda: service.rename_category(
            db_session, owner_a.id, category.id, name="ropa"
        ),
    )


def test_rename_to_a_name_used_in_the_other_kind_is_fine(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    create(db_session, owner_a, clock, "Otros", INCOME)
    category = create(db_session, owner_a, clock, "Varios", EXPENSE)
    assert (
        service.rename_category(db_session, owner_a.id, category.id, name="Otros").name
        == "Otros"
    )


def test_rename_changing_only_case_is_fine(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    category = create(db_session, owner_a, clock, "salud")
    assert (
        service.rename_category(db_session, owner_a.id, category.id, name="Salud").name
        == "Salud"
    )


def test_kind_cannot_be_changed(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    category = create(db_session, owner_a, clock, "Salud")
    with pytest.raises(TypeError):
        service.rename_category(  # type: ignore[call-arg]
            db_session, owner_a.id, category.id, name="Salud", kind=INCOME
        )


def test_list_filters_by_kind_and_shows_only_mine(
    db_session: Session, clock: FixedClock, owner_a: User, owner_b: User
) -> None:
    salud = create(db_session, owner_a, clock, "Salud")
    clock.advance(timedelta(seconds=1))
    arriendo = create(db_session, owner_a, clock, "Arriendo")
    salario = create(db_session, owner_a, clock, "Salario", INCOME)
    create(db_session, owner_b, clock, "De otro")

    assert service.list_categories(db_session, owner_a.id) == [
        arriendo,
        salario,
        salud,
    ]
    assert service.list_categories(db_session, owner_a.id, kind=EXPENSE) == [
        arriendo,
        salud,
    ]
    assert service.list_categories(db_session, owner_a.id, kind=INCOME) == [salario]


def test_category_of_another_user_looks_like_it_does_not_exist(
    db_session: Session, clock: FixedClock, owner_a: User, owner_b: User
) -> None:
    mine = create(db_session, owner_a, clock, "Salud")
    assert service.get_category(db_session, owner_a.id, mine.id) == mine
    for call in (
        lambda: service.get_category(db_session, owner_b.id, mine.id),
        lambda: service.rename_category(db_session, owner_b.id, mine.id, name="Mía"),
    ):
        expect(NotFound, "resource_not_found", "category_id", call)


# --- T29: archivar, desarchivar y borrar (RF-6, CL-31, CL-32) ---


def test_archive_and_unarchive(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    salud = create(db_session, owner_a, clock, "Salud")
    archived = service.archive_category(db_session, owner_a.id, clock, salud.id)
    assert archived.archived_at == clock.now()
    assert salud not in service.list_categories(db_session, owner_a.id)
    assert salud in service.list_categories(
        db_session, owner_a.id, include_archived=True
    )
    assert (
        service.unarchive_category(db_session, owner_a.id, salud.id).archived_at is None
    )
    assert salud in service.list_categories(db_session, owner_a.id)


def test_archived_category_keeps_its_movements(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_movement: Callable[..., Any],
) -> None:
    salud = create(db_session, owner_a, clock, "Salud")
    movement = make_movement(owner_a, category=salud)
    service.archive_category(db_session, owner_a.id, clock, salud.id)
    assert movement.category_id == salud.id


def test_archiving_twice_or_unarchiving_active_is_a_conflict(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    salud = create(db_session, owner_a, clock, "Salud")
    expect(
        Conflict,
        "not_archived",
        None,
        lambda: service.unarchive_category(db_session, owner_a.id, salud.id),
    )
    service.archive_category(db_session, owner_a.id, clock, salud.id)
    expect(
        Conflict,
        "already_archived",
        None,
        lambda: service.archive_category(db_session, owner_a.id, clock, salud.id),
    )


def test_cl_31_preloaded_category_never_used_can_be_deleted(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    from finanzas.services.bootstrap import seed_default_categories

    seed_default_categories(db_session, owner_a.id, clock)
    db_session.flush()
    suscripciones = next(
        c
        for c in service.list_categories(db_session, owner_a.id)
        if c.name == "Suscripciones"
    )
    service.delete_category(db_session, owner_a.id, suscripciones.id)
    expect(
        NotFound,
        "resource_not_found",
        "category_id",
        lambda: service.get_category(db_session, owner_a.id, suscripciones.id),
    )
    assert len(service.list_categories(db_session, owner_a.id)) == 15


@pytest.mark.parametrize("how", ["active", "cl_32_only_voided", "only_past_version"])
def test_used_category_cannot_be_deleted(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_movement: Callable[..., Any],
    how: str,
) -> None:
    salud = create(db_session, owner_a, clock, "Salud")
    otra = create(db_session, owner_a, clock, "Otra")
    movement = make_movement(owner_a, category=salud)
    if how == "cl_32_only_voided":
        movement.voided_at = clock.now()
    if how == "only_past_version":
        movement.category_id = otra.id  # solo su versión 1 recuerda «Salud»
    db_session.flush()
    expect(
        Conflict,
        "category_in_use",
        None,
        lambda: service.delete_category(db_session, owner_a.id, salud.id),
    )


@pytest.mark.parametrize("action", ["archive", "unarchive", "delete"])
def test_another_users_category_looks_like_it_does_not_exist(
    db_session: Session, clock: FixedClock, owner_a: User, owner_b: User, action: str
) -> None:
    mine = create(db_session, owner_a, clock, "Salud")
    call = {
        "archive": lambda: service.archive_category(
            db_session, owner_b.id, clock, mine.id
        ),
        "unarchive": lambda: service.unarchive_category(
            db_session, owner_b.id, mine.id
        ),
        "delete": lambda: service.delete_category(db_session, owner_b.id, mine.id),
    }[action]
    expect(NotFound, "resource_not_found", "category_id", call)
    assert service.get_category(db_session, owner_a.id, mine.id) == mine
