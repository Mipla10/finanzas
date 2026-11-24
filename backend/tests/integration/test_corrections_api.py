"""T47: API para corregir, anular e historial (RF-19, RF-20, RF-21, plan §4.3)."""

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from finanzas.db.models import Account, Category, Movement, User
from finanzas.domain.accounts import AccountType
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.movements import AdjustmentDirection, MovementType

URL = "/api/v1/movements"


def error_of(response: Any, status: int, error_type: str, field: str | None) -> None:
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert (error["type"], error["field"]) == (error_type, field)


@pytest.fixture
def nequi(owner_a: User, make_account: Callable[..., Account]) -> Account:
    return make_account(
        owner_a, AccountType.DIGITAL_WALLET, name="Nequi", initial_balance_cents=0
    )


@pytest.fixture
def m2(
    client: TestClient,
    owner_a: User,
    nequi: Account,
    make_category: Callable[..., Category],
) -> dict[str, Any]:
    """M2 del plan §2.4: primero con el monto equivocado."""
    domicilios = make_category(owner_a, CategoryKind.EXPENSE, name="Domicilios Prueba")
    response = client.post(
        URL,
        json={
            "type": "expense",
            "amount_cents": 2300000,
            "date": "2026-11-03",
            "from_account_id": str(nequi.id),
            "category_id": str(domicilios.id),
            "merchant": "rappi",
            "note": "Almuerzo",
        },
    )
    assert response.status_code == 201
    movement: dict[str, Any] = response.json()["movement"]
    return movement


# --- PATCH /movements/{id} ---


def test_patch_returns_changed_and_new_version_with_warnings(
    client: TestClient, m2: dict[str, Any], clock: FixedClock
) -> None:
    clock.advance(timedelta(hours=1))
    response = client.patch(f"{URL}/{m2['id']}", json={"amount_cents": 2500000})
    assert response.status_code == 200
    body = response.json()
    assert body["changed"] is True
    assert body["movement"]["version"] == 2
    assert body["movement"]["amount_cents"] == 2500000
    assert body["movement"]["created_at"] == m2["created_at"]  # no cambia
    assert [w["code"] for w in body["warnings"]] == ["negative_balance"]
    assert body["warnings"][0]["balance_cents"] == -2500000


def test_patch_without_real_change_returns_changed_false(
    client: TestClient, m2: dict[str, Any]
) -> None:
    response = client.patch(f"{URL}/{m2['id']}", json={"merchant": "RAPPI"})  # CL-24
    assert response.status_code == 200
    body = response.json()
    assert (body["changed"], body["movement"]["version"]) == (False, 1)
    assert body["warnings"] == []


def test_patch_null_clears_optional_text_but_omitted_keeps_it(
    client: TestClient, m2: dict[str, Any]
) -> None:
    body = client.patch(f"{URL}/{m2['id']}", json={"note": None}).json()
    assert body["changed"] is True
    assert body["movement"]["note"] is None
    assert body["movement"]["merchant"] == "rappi"  # no se envió: no cambia


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"type": "transfer"}, "type"),  # CL-21
        ({"amount_cents": 2500.5}, "amount_cents"),
        ({"amount_cents": None}, "amount_cents"),
        ({"date": "2026-11-24"}, "date"),
        ({"category_id": None}, "category_id"),
        ({"version": 3}, "version"),
    ],
)
def test_patch_invalid_is_422(
    client: TestClient, m2: dict[str, Any], changes: dict[str, Any], field: str
) -> None:
    error_of(
        client.patch(f"{URL}/{m2['id']}", json=changes), 422, "invalid_data", field
    )


def test_patch_voided_or_adjustment_is_409(
    client: TestClient,
    m2: dict[str, Any],
    owner_a: User,
    nequi: Account,
    make_movement: Callable[..., Movement],
) -> None:
    assert client.post(f"{URL}/{m2['id']}/void", json={}).status_code == 200
    voided = client.patch(f"{URL}/{m2['id']}", json={"amount_cents": 1})
    error_of(voided, 409, "conflict", None)  # CL-25

    adjustment = make_movement(
        owner_a,
        MovementType.ADJUSTMENT,
        adjustment_direction=AdjustmentDirection.IN,
        to_account=nequi,
    )
    response = client.patch(f"{URL}/{adjustment.id}", json={"amount_cents": 1})
    error_of(response, 409, "conflict", None)  # CL-18


# --- POST /movements/{id}/void ---


def test_void_returns_voided_true_with_moment_and_reason(
    client: TestClient, m2: dict[str, Any], clock: FixedClock
) -> None:
    clock.advance(timedelta(minutes=30))
    response = client.post(
        f"{URL}/{m2['id']}/void", json={"reason": "  Registrado dos veces "}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["movement"]["voided"] is True
    assert body["movement"]["voided_at"] == "2026-11-23T10:30:00-05:00"
    assert body["movement"]["void_reason"] == "Registrado dos veces"
    assert body["warnings"] == []  # Nequi vuelve a 0


def test_void_without_body_is_allowed(client: TestClient, m2: dict[str, Any]) -> None:
    response = client.post(f"{URL}/{m2['id']}/void")
    assert response.status_code == 200
    assert response.json()["movement"]["void_reason"] is None


def test_void_twice_is_409(client: TestClient, m2: dict[str, Any]) -> None:
    assert client.post(f"{URL}/{m2['id']}/void", json={}).status_code == 200
    error_of(client.post(f"{URL}/{m2['id']}/void", json={}), 409, "conflict", None)


def test_void_reason_too_long_is_422(client: TestClient, m2: dict[str, Any]) -> None:
    response = client.post(f"{URL}/{m2['id']}/void", json={"reason": "r" * 201})
    error_of(response, 422, "invalid_data", "reason")


# --- GET /movements/{id}/history ---


def test_history_has_the_plan_format(
    client: TestClient, m2: dict[str, Any], nequi: Account, clock: FixedClock
) -> None:
    clock.advance(timedelta(hours=2))
    client.patch(f"{URL}/{m2['id']}", json={"amount_cents": 2500000})
    response = client.get(f"{URL}/{m2['id']}/history")
    assert response.status_code == 200
    body = response.json()
    assert body["movement_id"] == m2["id"]
    assert body["voided"] is None
    first, second = body["versions"]
    assert first == {
        "version": 1,
        "created_at": "2026-11-23T10:00:00-05:00",
        "changed_fields": [],
        "amount_cents": 2300000,
        "date": "2026-11-03",
        "from_account": {"id": str(nequi.id), "name": "Nequi"},
        "to_account": None,
        "category": m2["category"],
        "merchant": "rappi",
        "note": "Almuerzo",
    }
    assert second["version"] == 2
    assert second["created_at"] == "2026-11-23T12:00:00-05:00"
    assert second["changed_fields"] == ["amount_cents"]
    assert second["amount_cents"] == 2500000


def test_history_ends_with_the_void(
    client: TestClient, m2: dict[str, Any], clock: FixedClock
) -> None:
    clock.advance(timedelta(days=1))
    client.post(f"{URL}/{m2['id']}/void", json={"reason": "Error"})
    body = client.get(f"{URL}/{m2['id']}/history").json()
    assert body["voided"] == {"at": "2026-11-24T10:00:00-05:00", "reason": "Error"}


# --- Otro usuario: igual que si no existiera (RF-22) ---


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("patch", "", {"amount_cents": 1}),
        ("post", "/void", {}),
        ("get", "/history", None),
    ],
)
def test_movement_of_other_owner_is_404_like_a_missing_one(
    client: TestClient,
    owner_b: User,
    make_movement: Callable[..., Movement],
    method: str,
    suffix: str,
    body: dict[str, Any] | None,
) -> None:
    def call(movement_id: uuid.UUID) -> Any:
        kwargs = {} if body is None else {"json": body}
        return client.request(method.upper(), f"{URL}/{movement_id}{suffix}", **kwargs)

    foreign = call(make_movement(owner_b).id)
    error_of(foreign, 404, "not_found", "movement_id")
    assert foreign.json() == call(uuid.uuid4()).json()
