"""T11: tablas users y accounts con sus reglas en la BD (RF-4, RNF-5, CL-33)."""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finanzas.db.models import Account, User
from finanzas.domain.accounts import AccountType

NOW = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)


def make_user(session: Session) -> User:
    user = User(id=uuid.uuid4(), created_at=NOW)
    session.add(user)
    session.flush()
    return user


def make_account(
    session: Session,
    owner: User,
    name: str,
    account_type: AccountType = AccountType.BANK,
    parent: Account | None = None,
) -> Account:
    account = Account(
        id=uuid.uuid4(),
        owner_id=owner.id,
        name=name,
        name_key=name.strip().casefold(),
        type=account_type,
        parent_id=parent.id if parent else None,
        initial_balance_cents=0,
        start_date=date(2026, 11, 1),
        created_at=NOW,
    )
    session.add(account)
    session.flush()
    return account


def test_bank_with_pocket_is_stored(db_session: Session) -> None:
    owner = make_user(db_session)
    bank = make_account(db_session, owner, "Banco Prueba")
    pocket = make_account(db_session, owner, "Ahorro", AccountType.POCKET, bank)
    assert pocket.parent_id == bank.id


def test_pocket_without_parent_is_rejected(db_session: Session) -> None:
    owner = make_user(db_session)
    with pytest.raises(IntegrityError, match="ck_accounts_pocket_has_parent"):
        make_account(db_session, owner, "Bolsillo huérfano", AccountType.POCKET)


def test_non_pocket_with_parent_is_rejected(db_session: Session) -> None:
    owner = make_user(db_session)
    bank = make_account(db_session, owner, "Banco Prueba")
    with pytest.raises(IntegrityError, match="ck_accounts_pocket_has_parent"):
        make_account(db_session, owner, "Billetera", AccountType.DIGITAL_WALLET, bank)


def test_duplicate_name_for_same_owner_is_rejected(db_session: Session) -> None:
    owner = make_user(db_session)
    make_account(db_session, owner, "Billetera Prueba")
    with pytest.raises(IntegrityError, match="uq_accounts_owner_id_name_key"):
        make_account(db_session, owner, "billetera prueba")


def test_same_name_for_other_owner_is_accepted(db_session: Session) -> None:
    owner_a, owner_b = make_user(db_session), make_user(db_session)
    make_account(db_session, owner_a, "Billetera Prueba")
    make_account(db_session, owner_b, "Billetera Prueba")


def test_parent_of_another_owner_is_rejected(db_session: Session) -> None:
    owner_a, owner_b = make_user(db_session), make_user(db_session)
    bank_of_a = make_account(db_session, owner_a, "Banco de A")
    with pytest.raises(IntegrityError, match="fk_accounts_parent_owner"):
        make_account(
            db_session, owner_b, "Bolsillo de B", AccountType.POCKET, bank_of_a
        )


def test_account_cannot_be_its_own_parent(db_session: Session) -> None:
    owner = make_user(db_session)
    account_id = uuid.uuid4()
    account = Account(
        id=account_id,
        owner_id=owner.id,
        name="Circular",
        name_key="circular",
        type=AccountType.POCKET,
        parent_id=account_id,
        initial_balance_cents=0,
        start_date=date(2026, 11, 1),
        created_at=NOW,
    )
    db_session.add(account)
    with pytest.raises(IntegrityError, match="ck_accounts_not_own_parent"):
        db_session.flush()
