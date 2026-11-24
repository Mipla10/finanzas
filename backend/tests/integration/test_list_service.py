"""T39–T40: listar, filtrar, paginar y totalizar (RF-17, CL-35 a CL-38, plan §5.1)."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, User
from finanzas.domain.accounts import AccountType
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.errors import DomainError, InvalidData, NotFound
from finanzas.domain.movements import MovementType
from finanzas.services import movements as service

T = MovementType


def expect(
    error: type[DomainError], code: str, field: str | None, call: Callable[[], Any]
) -> None:
    with pytest.raises(error) as caught:
        call()
    assert (caught.value.code, caught.value.field) == (code, field)


@dataclass
class Book:
    """Cuentas y categorías de un usuario para los escenarios de listado."""

    lulo: Account
    ahorro: Account
    nequi: Account
    cash: Account
    food: Category
    salary: Category


@pytest.fixture
def book(
    owner_a: User,
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> Book:
    lulo = make_account(owner_a, name="Lulo Prueba")
    return Book(
        lulo=lulo,
        ahorro=make_account(
            owner_a, AccountType.POCKET, name="Ahorro Prueba", parent=lulo
        ),
        nequi=make_account(owner_a, AccountType.DIGITAL_WALLET, name="Nequi Prueba"),
        cash=make_account(owner_a, AccountType.CASH, name="Efectivo Prueba"),
        food=make_category(owner_a, CategoryKind.EXPENSE, name="Comida Prueba"),
        salary=make_category(owner_a, CategoryKind.INCOME, name="Salario Prueba"),
    )


def ids(page: Any) -> list[uuid.UUID]:
    return [m.id for m in page.items]


def listing(session: Session, owner: User, **filters: Any) -> Any:
    return service.list_movements(session, owner.id, **filters)


# --- T39: orden, filtros y paginación ---


def test_order_is_date_then_registration_then_id_descending(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    book: Book,
    make_movement: Callable[..., Movement],
) -> None:
    old = make_movement(owner_a, from_account=book.nequi, on=date(2026, 11, 2))
    first_today = make_movement(owner_a, from_account=book.nequi)
    clock.advance(timedelta(minutes=5))
    twins = [make_movement(owner_a, from_account=book.nequi) for _ in range(2)]

    expected_twins = sorted((m.id for m in twins), reverse=True)  # mismo instante
    assert ids(listing(db_session, owner_a)) == [
        *expected_twins,
        first_today.id,
        old.id,
    ]


def test_cl_35_filter_by_account_includes_transfers_in_both_directions(
    db_session: Session,
    owner_a: User,
    book: Book,
    make_movement: Callable[..., Movement],
) -> None:
    out = make_movement(
        owner_a, T.TRANSFER, from_account=book.nequi, to_account=book.cash
    )
    into = make_movement(
        owner_a, T.TRANSFER, from_account=book.lulo, to_account=book.nequi
    )
    spent = make_movement(owner_a, from_account=book.nequi, category=book.food)
    make_movement(owner_a, from_account=book.cash, category=book.food)  # otra cuenta

    found = set(ids(listing(db_session, owner_a, account_ids=[book.nequi.id])))
    assert found == {out.id, into.id, spent.id}


def test_cl_36_filter_by_bank_excludes_its_pockets(
    db_session: Session,
    owner_a: User,
    book: Book,
    make_movement: Callable[..., Movement],
) -> None:
    in_lulo = make_movement(owner_a, from_account=book.lulo, category=book.food)
    make_movement(owner_a, from_account=book.ahorro, category=book.food)
    assert ids(listing(db_session, owner_a, account_ids=[book.lulo.id])) == [in_lulo.id]


def test_cl_37_date_range_includes_both_ends(
    db_session: Session,
    owner_a: User,
    book: Book,
    make_movement: Callable[..., Movement],
) -> None:
    def on(day: int) -> Movement:
        return make_movement(owner_a, from_account=book.nequi, on=date(2026, 11, day))

    first, last = on(1), on(3)
    on(4)  # fuera del rango
    page = listing(
        db_session, owner_a, date_from=date(2026, 11, 1), date_to=date(2026, 11, 3)
    )
    assert set(ids(page)) == {first.id, last.id}


def test_filter_by_category_and_by_several_types(
    db_session: Session,
    owner_a: User,
    book: Book,
    make_movement: Callable[..., Movement],
) -> None:
    expense = make_movement(owner_a, from_account=book.nequi, category=book.food)
    income = make_movement(
        owner_a, T.INCOME, to_account=book.nequi, category=book.salary
    )
    yielded = make_movement(owner_a, T.YIELD, to_account=book.ahorro)
    make_movement(owner_a, T.TRANSFER, from_account=book.lulo, to_account=book.cash)

    by_category = listing(
        db_session, owner_a, category_ids=[book.food.id, book.salary.id]
    )
    assert set(ids(by_category)) == {expense.id, income.id}  # sin tipos sin categoría
    by_types = listing(db_session, owner_a, types=[T.INCOME, T.YIELD])
    assert set(ids(by_types)) == {income.id, yielded.id}


def test_voided_are_excluded_unless_asked(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    book: Book,
    make_movement: Callable[..., Movement],
) -> None:
    kept = make_movement(owner_a, from_account=book.nequi)
    voided = make_movement(owner_a, from_account=book.nequi)
    voided.voided_at = clock.now()
    db_session.flush()
    assert ids(listing(db_session, owner_a)) == [kept.id]
    assert set(ids(listing(db_session, owner_a, include_voided=True))) == {
        kept.id,
        voided.id,
    }


def test_limit_and_offset_with_total(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    book: Book,
    make_movement: Callable[..., Movement],
) -> None:
    created = []
    for _ in range(5):
        created.append(make_movement(owner_a, from_account=book.nequi))
        clock.advance(timedelta(seconds=1))
    newest_first = [m.id for m in reversed(created)]

    first = listing(db_session, owner_a, limit=2)
    second = listing(db_session, owner_a, limit=2, offset=2)
    assert (first.limit, first.offset, first.total_items) == (2, 0, 5)
    assert ids(first) == newest_first[:2]
    assert ids(second) == newest_first[2:4]
    assert listing(db_session, owner_a).limit == 50  # valor por defecto


def test_only_my_movements_are_listed(
    db_session: Session,
    owner_a: User,
    owner_b: User,
    book: Book,
    make_movement: Callable[..., Movement],
) -> None:
    mine = make_movement(owner_a, from_account=book.nequi)
    make_movement(owner_b)
    assert ids(listing(db_session, owner_a)) == [mine.id]


@pytest.mark.parametrize(
    ("filters", "code", "field"),
    [
        (
            {"date_from": date(2026, 11, 5), "date_to": date(2026, 11, 1)},
            "date_range_inverted",
            "date_from",
        ),
        ({"limit": 0}, "ge", "limit"),
        ({"limit": 201}, "le", "limit"),
        ({"offset": -1}, "ge", "offset"),
    ],
)
def test_invalid_filters_are_rejected(
    db_session: Session,
    owner_a: User,
    filters: dict[str, Any],
    code: str,
    field: str,
) -> None:
    expect(InvalidData, code, field, lambda: listing(db_session, owner_a, **filters))


@pytest.mark.parametrize("kind", ["account_ids", "category_ids"])
@pytest.mark.parametrize("whose", ["nonexistent", "other_user"])
def test_unknown_or_foreign_filter_ids_look_like_they_do_not_exist(
    db_session: Session,
    owner_a: User,
    owner_b: User,
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    kind: str,
    whose: str,
) -> None:
    if whose == "nonexistent":
        foreign = uuid.uuid4()
    elif kind == "account_ids":
        foreign = make_account(owner_b).id
    else:
        foreign = make_category(owner_b).id
    field = kind.removesuffix("s")
    expect(
        NotFound,
        "resource_not_found",
        field,
        lambda: listing(db_session, owner_a, **{kind: [foreign]}),
    )
