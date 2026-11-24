"""T23: crear y consultar cuentas (RF-4, CL-10, CL-13, CL-33, CL-34)."""

import uuid
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from finanzas.db.models import Account, User
from finanzas.domain.accounts import AccountType
from finanzas.domain.dates import FixedClock
from finanzas.domain.errors import Conflict, DomainError, InvalidData, NotFound
from finanzas.services import accounts as service


def create(session: Session, owner: User, clock: FixedClock, **fields: Any) -> Account:
    values: dict[str, Any] = {
        "name": "Banco Prueba",
        "account_type": AccountType.BANK,
        "initial_balance_cents": 0,
    }
    values.update(fields)
    return service.create_account(session, owner.id, clock, **values)


def expect(
    error: type[DomainError], code: str, field: str | None, call: Callable[[], Any]
) -> None:
    with pytest.raises(error) as caught:
        call()
    assert (caught.value.code, caught.value.field) == (code, field)


# --- Crear ---


def test_create_the_four_accounts_of_the_plan_example(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    start = date(2026, 11, 1)
    lulo = create(
        db_session,
        owner_a,
        clock,
        name="Lulo",
        initial_balance_cents=150000000,
        start_date=start,
    )
    ahorro = create(
        db_session,
        owner_a,
        clock,
        name="Ahorro",
        account_type=AccountType.POCKET,
        parent_id=lulo.id,
        initial_balance_cents=300000000,
        start_date=start,
    )
    nequi = create(
        db_session,
        owner_a,
        clock,
        name="Nequi",
        account_type=AccountType.DIGITAL_WALLET,
        initial_balance_cents=20000000,
    )
    efectivo = create(
        db_session,
        owner_a,
        clock,
        name="  Efectivo  ",
        account_type=AccountType.CASH,
        initial_balance_cents=5000000,
    )
    assert ahorro.parent_id == lulo.id
    assert (efectivo.name, efectivo.name_key) == ("Efectivo", "efectivo")
    assert nequi.start_date == clock.today()  # sin fecha → hoy
    assert lulo.created_at == clock.now()
    assert all(a.owner_id == owner_a.id for a in (lulo, ahorro, nequi, efectivo))


@pytest.mark.parametrize("balance", [0, -500000])
def test_cl_13_initial_balance_zero_or_negative_is_accepted(
    db_session: Session, clock: FixedClock, owner_a: User, balance: int
) -> None:
    account = create(db_session, owner_a, clock, initial_balance_cents=balance)
    assert account.initial_balance_cents == balance


def test_cl_10_future_start_date_is_rejected(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    expect(
        InvalidData,
        "start_date_in_future",
        "start_date",
        lambda: create(
            db_session, owner_a, clock, start_date=clock.today() + timedelta(days=1)
        ),
    )


def test_cl_33_duplicate_name_ignoring_case_is_a_conflict(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    create(db_session, owner_a, clock, name="Nequi")
    expect(
        Conflict,
        "duplicate_account_name",
        "name",
        lambda: create(db_session, owner_a, clock, name=" nequi "),
    )


def test_same_name_for_another_user_is_fine(
    db_session: Session, clock: FixedClock, owner_a: User, owner_b: User
) -> None:
    create(db_session, owner_a, clock, name="Nequi")
    assert create(db_session, owner_b, clock, name="Nequi").owner_id == owner_b.id


@pytest.mark.parametrize(
    ("fields", "error", "code", "field"),
    [
        ({"name": "   "}, InvalidData, "required", "name"),
        ({"name": "x" * 61}, InvalidData, "too_long", "name"),
        (
            {"initial_balance_cents": 10.5},
            InvalidData,
            "amount_not_integer",
            "initial_balance_cents",
        ),
        ({"account_type": AccountType.POCKET}, InvalidData, "required", "parent_id"),
    ],
)
def test_invalid_data_is_rejected(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    fields: dict[str, Any],
    error: type[DomainError],
    code: str,
    field: str,
) -> None:
    expect(error, code, field, lambda: create(db_session, owner_a, clock, **fields))


def test_only_pockets_can_have_a_parent(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    bank = create(db_session, owner_a, clock, name="Lulo")
    expect(
        InvalidData,
        "parent_only_for_pocket",
        "parent_id",
        lambda: create(
            db_session,
            owner_a,
            clock,
            name="Nequi",
            account_type=AccountType.DIGITAL_WALLET,
            parent_id=bank.id,
        ),
    )


def test_cl_34_pocket_cannot_hang_from_another_pocket(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    bank = create(db_session, owner_a, clock, name="Lulo")
    pocket = create(
        db_session,
        owner_a,
        clock,
        name="Ahorro",
        account_type=AccountType.POCKET,
        parent_id=bank.id,
    )
    expect(
        InvalidData,
        "parent_must_be_bank",
        "parent_id",
        lambda: create(
            db_session,
            owner_a,
            clock,
            name="Sub-bolsillo",
            account_type=AccountType.POCKET,
            parent_id=pocket.id,
        ),
    )


def test_archived_parent_is_a_conflict(
    db_session: Session, clock: FixedClock, owner_a: User
) -> None:
    bank = create(db_session, owner_a, clock, name="Lulo")
    bank.archived_at = clock.now()
    db_session.flush()
    expect(
        Conflict,
        "parent_archived",
        "parent_id",
        lambda: create(
            db_session,
            owner_a,
            clock,
            name="Ahorro",
            account_type=AccountType.POCKET,
            parent_id=bank.id,
        ),
    )


@pytest.mark.parametrize("parent", ["of_other_user", "nonexistent"])
def test_parent_of_another_user_looks_like_it_does_not_exist(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    owner_b: User,
    make_account: Callable[..., Account],
    parent: str,
) -> None:
    parent_id = make_account(owner_b).id if parent == "of_other_user" else uuid.uuid4()
    expect(
        NotFound,
        "resource_not_found",
        "parent_id",
        lambda: create(
            db_session,
            owner_a,
            clock,
            name="Ahorro",
            account_type=AccountType.POCKET,
            parent_id=parent_id,
        ),
    )


# --- Consultar ---


def test_list_returns_only_my_active_accounts_in_creation_order(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    owner_b: User,
) -> None:
    first = create(db_session, owner_a, clock, name="Lulo")
    clock.advance(timedelta(seconds=1))
    second = create(db_session, owner_a, clock, name="Nequi")
    clock.advance(timedelta(seconds=1))
    archived = create(db_session, owner_a, clock, name="Vieja")
    archived.archived_at = clock.now()
    create(db_session, owner_b, clock, name="De otro")
    db_session.flush()

    assert service.list_accounts(db_session, owner_a.id) == [first, second]
    assert service.list_accounts(db_session, owner_a.id, include_archived=True) == [
        first,
        second,
        archived,
    ]


def test_get_account_of_another_user_looks_like_it_does_not_exist(
    db_session: Session, clock: FixedClock, owner_a: User, owner_b: User
) -> None:
    mine = create(db_session, owner_a, clock)
    assert service.get_account(db_session, owner_a.id, mine.id) == mine
    expect(
        NotFound,
        "resource_not_found",
        "account_id",
        lambda: service.get_account(db_session, owner_b.id, mine.id),
    )
