"""T45: API para crear y ver movimientos (RF-1, RF-18, CL-7, CL-11, plan §4.3)."""

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, User
from finanzas.domain.accounts import AccountType
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.movements import MovementType
from finanzas.services import movements as service

URL = "/api/v1/movements"


def error_of(response: Any, status: int, error_type: str, field: str | None) -> None:
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert (error["type"], error["field"]) == (error_type, field)


@pytest.fixture
def nequi(owner_a: User, make_account: Callable[..., Account]) -> Account:
    return make_account(
        owner_a,
        AccountType.DIGITAL_WALLET,
        name="Nequi",
        initial_balance_cents=20000000,
    )


@pytest.fixture
def domicilios(owner_a: User, make_category: Callable[..., Category]) -> Category:
    return make_category(owner_a, CategoryKind.EXPENSE, name="Domicilios Prueba")


def expense_body(
    nequi: Account, domicilios: Category, **changes: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "expense",
        "amount_cents": 2500000,
        "date": "2026-11-03",
        "from_account_id": str(nequi.id),
        "category_id": str(domicilios.id),
        "merchant": "  rappi ",
        "note": "Almuerzo",
    }
    body.update(changes)
    return body


# --- POST /movements ---


def test_create_expense_returns_201_with_the_plan_example_json(
    client: TestClient, nequi: Account, domicilios: Category
) -> None:
    response = client.post(URL, json=expense_body(nequi, domicilios))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["warnings"] == []
    movement = body["movement"]
    uuid.UUID(movement.pop("id"))
    assert movement == {
        "type": "expense",
        "amount_cents": 2500000,
        "date": "2026-11-03",
        "from_account": {"id": str(nequi.id), "name": "Nequi"},
        "to_account": None,
        "category": {"id": str(domicilios.id), "name": "Domicilios Prueba"},
        "adjustment_direction": None,
        "merchant": "rappi",
        "note": "Almuerzo",
        "voided": False,
        "voided_at": None,
        "void_reason": None,
        "version": 1,
        "created_at": "2026-11-23T10:00:00-05:00",
    }


def test_create_without_date_uses_today(
    client: TestClient, nequi: Account, domicilios: Category
) -> None:
    body = expense_body(nequi, domicilios)
    del body["date"]
    response = client.post(URL, json=body)
    assert response.status_code == 201
    assert response.json()["movement"]["date"] == "2026-11-23"


def test_transfer_that_leaves_negative_balance_returns_201_with_warning(
    client: TestClient,
    owner_a: User,
    nequi: Account,
    make_account: Callable[..., Account],
) -> None:
    efectivo = make_account(owner_a, AccountType.CASH, name="Efectivo Prueba")
    response = client.post(
        URL,
        json={
            "type": "transfer",
            "amount_cents": 92850000,
            "from_account_id": str(nequi.id),
            "to_account_id": str(efectivo.id),
        },
    )
    assert response.status_code == 201
    assert response.json()["warnings"] == [
        {
            "code": "negative_balance",
            "account": {"id": str(nequi.id), "name": "Nequi"},
            "balance_cents": -72850000,
            "message": "La cuenta Nequi quedó con saldo negativo.",
        }
    ]


def test_cl_7_february_31_is_422(
    client: TestClient, nequi: Account, domicilios: Category
) -> None:
    response = client.post(URL, json=expense_body(nequi, domicilios, date="2026-02-31"))
    error_of(response, 422, "invalid_data", "date")


@pytest.mark.parametrize("amount", [0, -500000, 2500.5, "25.000", 2500000.0, 2**53])
def test_cl_11_invalid_amounts_are_422(
    client: TestClient, nequi: Account, domicilios: Category, amount: Any
) -> None:
    response = client.post(
        URL, json=expense_body(nequi, domicilios, amount_cents=amount)
    )
    error_of(response, 422, "invalid_data", "amount_cents")


@pytest.mark.parametrize(
    ("changes", "status", "error_type", "field"),
    [
        ({"date": "2026-11-24"}, 422, "invalid_data", "date"),  # futura
        ({"type": "adjustment"}, 422, "invalid_data", "type"),
        ({"type": "gasto"}, 422, "invalid_data", "type"),
        ({"to_account_id": None, "category_id": None}, 422, "invalid_data", None),
        ({"merchant": "m" * 81}, 422, "invalid_data", "merchant"),
        ({"note": "n" * 501}, 422, "invalid_data", "note"),
        ({"hour": "10:00"}, 422, "invalid_data", "hour"),
        ({"from_account_id": str(uuid.uuid4())}, 404, "not_found", "from_account_id"),
    ],
)
def test_create_rejections(
    client: TestClient,
    nequi: Account,
    domicilios: Category,
    changes: dict[str, Any],
    status: int,
    error_type: str,
    field: str | None,
) -> None:
    if field is None:  # forma inválida: un gasto sin categoría
        field = "category_id"
    response = client.post(URL, json=expense_body(nequi, domicilios, **changes))
    error_of(response, status, error_type, field)


def test_create_with_account_of_other_owner_is_404(
    client: TestClient,
    owner_b: User,
    domicilios: Category,
    make_account: Callable[..., Account],
) -> None:
    foreign = make_account(owner_b)
    response = client.post(URL, json=expense_body(foreign, domicilios))
    error_of(response, 404, "not_found", "from_account_id")


# --- GET /movements/{id} ---


def test_get_returns_all_data_of_a_current_movement(
    client: TestClient, nequi: Account, domicilios: Category
) -> None:
    created = client.post(URL, json=expense_body(nequi, domicilios)).json()
    response = client.get(f"{URL}/{created['movement']['id']}")
    assert response.status_code == 200
    assert response.json() == created["movement"]


def test_get_voided_movement_shows_moment_and_reason(
    client: TestClient,
    db_session: Session,
    owner_a: User,
    clock: FixedClock,
    make_movement: Callable[..., Movement],
) -> None:
    movement = make_movement(owner_a, MovementType.YIELD, amount_cents=123456)
    clock.advance(timedelta(minutes=5))
    service.void_movement(
        db_session, owner_a.id, clock, movement.id, reason="Registrado dos veces"
    )
    body = client.get(f"{URL}/{movement.id}").json()
    assert (body["type"], body["amount_cents"]) == ("yield", 123456)
    assert body["voided"] is True
    assert body["voided_at"] == "2026-11-23T10:05:00-05:00"
    assert body["void_reason"] == "Registrado dos veces"
    assert body["category"] is None and body["from_account"] is None


def test_get_movement_of_other_owner_is_404_like_a_missing_one(
    client: TestClient, owner_b: User, make_movement: Callable[..., Movement]
) -> None:
    foreign = client.get(f"{URL}/{make_movement(owner_b).id}")
    missing = client.get(f"{URL}/{uuid.uuid4()}")
    error_of(foreign, 404, "not_found", "movement_id")
    assert foreign.json() == missing.json()
