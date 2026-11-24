"""T22: usuario inicial y categorías precargadas (RF-3, plan §5.4)."""

import uuid

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finanzas import main
from finanzas.api.deps import get_owner_id
from finanzas.config import Settings
from finanzas.db.models import Category, User
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.defaults import DEFAULT_CATEGORIES
from finanzas.services.bootstrap import ensure_initial_user

EXPENSES = [
    "Alimentación",
    "Domicilios",
    "Transporte",
    "Vivienda",
    "Servicios",
    "Salud",
    "Educación",
    "Entretenimiento",
    "Ropa",
    "Suscripciones",
    "Comisiones bancarias",
    "Otros",
]
INCOMES = ["Salario", "Freelance", "Regalos", "Otros"]


def test_default_categories_are_exactly_those_of_the_spec() -> None:
    assert [n for n, k in DEFAULT_CATEGORIES if k is CategoryKind.EXPENSE] == EXPENSES
    assert [n for n, k in DEFAULT_CATEGORIES if k is CategoryKind.INCOME] == INCOMES


def test_empty_database_gets_one_user_with_16_categories(
    db_session: Session, clock: FixedClock
) -> None:
    assert db_session.scalar(select(func.count()).select_from(User)) == 0

    owner_id = ensure_initial_user(db_session, clock)

    users = db_session.scalars(select(User)).all()
    assert [u.id for u in users] == [owner_id]
    assert users[0].created_at == clock.now()
    categories = db_session.scalars(
        select(Category).where(Category.owner_id == owner_id)
    ).all()
    by_kind = {
        kind: sorted(c.name for c in categories if c.kind is kind)
        for kind in CategoryKind
    }
    assert by_kind[CategoryKind.EXPENSE] == sorted(EXPENSES)
    assert by_kind[CategoryKind.INCOME] == sorted(INCOMES)
    assert all(c.archived_at is None for c in categories)
    assert {c.name_key for c in categories} >= {"alimentación", "otros"}


def test_running_it_again_creates_nothing_new(
    db_session: Session, clock: FixedClock
) -> None:
    first = ensure_initial_user(db_session, clock)
    second = ensure_initial_user(db_session, clock)
    assert first == second
    assert db_session.scalar(select(func.count()).select_from(User)) == 1
    assert db_session.scalar(select(func.count()).select_from(Category)) == 16


def test_app_seeds_at_startup_and_get_owner_id_returns_that_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = uuid.uuid4()
    calls: list[object] = []

    def fake_ensure_initial_user(session: Session, clock: object) -> uuid.UUID:
        calls.append(clock)
        return seeded

    monkeypatch.setattr(main, "ensure_initial_user", fake_ensure_initial_user)

    whoami = APIRouter()

    @whoami.get("/whoami")
    def who(owner_id: uuid.UUID = Depends(get_owner_id)) -> dict[str, str]:  # noqa: B008
        return {"owner_id": str(owner_id)}

    settings = Settings(_env_file=None, app_password="clave-de-prueba-12")
    app = main.create_app(settings, protected_routers=[whoami])
    with TestClient(app) as client:  # «with» = arranca y apaga la app (lifespan)
        response = client.get(
            f"{main.API_PREFIX}/whoami",
            headers={"Authorization": "Bearer clave-de-prueba-12"},
        )
    assert len(calls) == 1  # la siembra corre una vez al arrancar
    assert response.json() == {"owner_id": str(seeded)}
