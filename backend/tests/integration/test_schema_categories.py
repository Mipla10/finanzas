"""T12: tabla categories con nombre único por usuario y clase (RF-6, RNF-5)."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finanzas.db.models import Category, User
from finanzas.domain.categories import CategoryKind

NOW = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)


def make_user(session: Session) -> User:
    user = User(id=uuid.uuid4(), created_at=NOW)
    session.add(user)
    session.flush()
    return user


def make_category(
    session: Session, owner: User, name: str, kind: CategoryKind
) -> Category:
    category = Category(
        id=uuid.uuid4(),
        owner_id=owner.id,
        name=name,
        name_key=name.strip().casefold(),
        kind=kind,
        created_at=NOW,
    )
    session.add(category)
    session.flush()
    return category


def test_category_is_stored_with_its_kind(db_session: Session) -> None:
    owner = make_user(db_session)
    category = make_category(db_session, owner, "Domicilios", CategoryKind.EXPENSE)
    db_session.expire(category)
    assert category.kind is CategoryKind.EXPENSE
    assert category.archived_at is None


def test_duplicate_name_in_same_kind_is_rejected(db_session: Session) -> None:
    owner = make_user(db_session)
    make_category(db_session, owner, "Comercio X", CategoryKind.EXPENSE)
    with pytest.raises(IntegrityError, match="uq_categories_owner_id_kind_name_key"):
        make_category(db_session, owner, "comercio x", CategoryKind.EXPENSE)


def test_same_name_in_other_kind_is_accepted(db_session: Session) -> None:
    owner = make_user(db_session)
    make_category(db_session, owner, "Otros", CategoryKind.EXPENSE)
    make_category(db_session, owner, "Otros", CategoryKind.INCOME)


def test_same_name_for_other_owner_is_accepted(db_session: Session) -> None:
    owner_a, owner_b = make_user(db_session), make_user(db_session)
    make_category(db_session, owner_a, "Otros", CategoryKind.EXPENSE)
    make_category(db_session, owner_b, "Otros", CategoryKind.EXPENSE)


def test_category_needs_an_existing_owner(db_session: Session) -> None:
    ghost = User(id=uuid.uuid4(), created_at=NOW)  # nunca se guarda
    with pytest.raises(IntegrityError, match="fk_categories_owner_id_users"):
        make_category(db_session, ghost, "Sin dueño", CategoryKind.INCOME)
