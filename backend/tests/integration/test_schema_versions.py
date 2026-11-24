"""T14: tabla movement_versions, solo de inserción (RF-20, RNF-2, RNF-5)."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Movement, MovementVersion, User
from finanzas.domain.accounts import AccountType
from finanzas.domain.movements import MovementType

NOW = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)


def make_owner_with_yield(session: Session, label: str) -> tuple[User, Movement]:
    """Un usuario con una cuenta y un rendimiento (el tipo más simple)."""
    owner = User(id=uuid.uuid4(), created_at=NOW)
    session.add(owner)
    session.flush()
    account = Account(
        id=uuid.uuid4(),
        owner_id=owner.id,
        name=f"Banco {label}",
        name_key=f"banco {label}".casefold(),
        type=AccountType.BANK,
        initial_balance_cents=0,
        start_date=date(2026, 11, 1),
        created_at=NOW,
    )
    session.add(account)
    session.flush()
    movement = Movement(
        id=uuid.uuid4(),
        owner_id=owner.id,
        type=MovementType.YIELD,
        amount_cents=123456,
        date=date(2026, 11, 20),
        to_account_id=account.id,
        created_at=NOW,
        updated_at=NOW,
        current_version=1,
    )
    session.add(movement)
    session.flush()
    return owner, movement


def make_version(
    session: Session, owner: User, movement: Movement, version_no: int, **extra: Any
) -> MovementVersion:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "owner_id": owner.id,
        "movement_id": movement.id,
        "version_no": version_no,
        "amount_cents": movement.amount_cents,
        "date": movement.date,
        "to_account_id": movement.to_account_id,
        "changed_fields": [] if version_no == 1 else ["amount_cents"],
        "created_at": NOW,
    }
    values.update(extra)
    version = MovementVersion(**values)
    session.add(version)
    session.flush()
    return version


def test_versions_are_stored_with_changed_fields(db_session: Session) -> None:
    owner, movement = make_owner_with_yield(db_session, "A")
    make_version(db_session, owner, movement, 1)
    second = make_version(db_session, owner, movement, 2, amount_cents=200000)
    db_session.expire(second)
    assert second.changed_fields == ["amount_cents"]
    assert second.amount_cents == 200000


def test_duplicate_version_number_is_rejected(db_session: Session) -> None:
    owner, movement = make_owner_with_yield(db_session, "A")
    make_version(db_session, owner, movement, 1)
    with pytest.raises(
        IntegrityError, match="uq_movement_versions_movement_id_version_no"
    ):
        make_version(db_session, owner, movement, 1)


def test_version_numbers_start_at_one(db_session: Session) -> None:
    owner, movement = make_owner_with_yield(db_session, "A")
    with pytest.raises(IntegrityError, match="ck_movement_versions_version_positive"):
        make_version(db_session, owner, movement, 0)


def test_version_of_another_owners_movement_is_rejected(db_session: Session) -> None:
    owner_a, movement_of_a = make_owner_with_yield(db_session, "A")
    owner_b, _ = make_owner_with_yield(db_session, "B")
    with pytest.raises(IntegrityError, match="fk_movement_versions_movement_owner"):
        make_version(db_session, owner_b, movement_of_a, 1)


def test_version_cannot_reference_another_owners_account(db_session: Session) -> None:
    owner_a, movement_of_a = make_owner_with_yield(db_session, "A")
    _, movement_of_b = make_owner_with_yield(db_session, "B")
    with pytest.raises(IntegrityError, match="fk_movement_versions_to_account_owner"):
        make_version(
            db_session,
            owner_a,
            movement_of_a,
            1,
            to_account_id=movement_of_b.to_account_id,
        )
