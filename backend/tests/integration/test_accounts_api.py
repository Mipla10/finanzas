"""T43: API de cuentas (RF-4, RF-5, plan §4.2, §4.3)."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from finanzas.api import deps
from finanzas.db.models import Account, Movement, User
from finanzas.domain.accounts import AccountType
from finanzas.domain.dates import SystemClock
from finanzas.domain.movements import MovementType

URL = "/api/v1/accounts"


def error_of(response: Any, status: int, error_type: str, field: str | None) -> None:
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert (error["type"], error["field"]) == (error_type, field)
    assert set(error) == {"type", "field", "message", "details"}


def create(client: TestClient, **fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Banco Prueba",
        "type": "bank",
        "initial_balance_cents": 0,
    }
    body.update(fields)
    response = client.post(URL, json=body)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


# --- POST /accounts ---


def test_create_pocket_returns_201_with_the_plan_example_json(
    client: TestClient,
) -> None:
    lulo = create(client, name="Lulo", start_date="2026-11-01")
    response = client.post(
        URL,
        json={
            "name": "Ahorro",
            "type": "pocket",
            "parent_id": lulo["id"],
            "initial_balance_cents": 300000000,
            "start_date": "2026-11-01",
        },
    )
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body.pop("id"))
    assert body == {
        "name": "Ahorro",
        "type": "pocket",
        "parent_id": lulo["id"],
        "initial_balance_cents": 300000000,
        "start_date": "2026-11-01",
        "archived": False,
        "created_at": "2026-11-23T10:00:00-05:00",
    }


def test_create_without_start_date_uses_today(client: TestClient) -> None:
    assert create(client)["start_date"] == "2026-11-23"


def test_create_duplicate_name_is_409(client: TestClient) -> None:
    create(client, name="Nequi", type="digital_wallet")
    response = client.post(
        URL, json={"name": " nequi ", "type": "cash", "initial_balance_cents": 0}
    )
    error_of(response, 409, "conflict", "name")


def test_create_pocket_with_parent_of_other_owner_is_404(
    client: TestClient, owner_b: User, make_account: Callable[..., Account]
) -> None:
    foreign = make_account(owner_b)
    response = client.post(
        URL,
        json={
            "name": "Bolsillo",
            "type": "pocket",
            "parent_id": str(foreign.id),
            "initial_balance_cents": 0,
        },
    )
    error_of(response, 404, "not_found", "parent_id")


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"initial_balance_cents": 2500.5}, "initial_balance_cents"),
        ({"initial_balance_cents": "2500000"}, "initial_balance_cents"),
        ({"initial_balance_cents": 2**53}, "initial_balance_cents"),
        ({"type": "credit_card"}, "type"),
        ({"start_date": "2026-11-24"}, "start_date"),  # futura (CL-10)
        ({"start_date": "2026-02-31"}, "start_date"),
        ({"name": "   "}, "name"),
        ({"name": "x" * 61}, "name"),
        ({"balance": 5}, "balance"),  # campo que no existe
    ],
)
def test_create_with_invalid_data_is_422(
    client: TestClient, changes: dict[str, Any], field: str
) -> None:
    body = {"name": "Banco Prueba", "type": "bank", "initial_balance_cents": 0}
    body.update(changes)
    error_of(client.post(URL, json=body), 422, "invalid_data", field)


def test_create_without_name_is_422(client: TestClient) -> None:
    response = client.post(URL, json={"type": "bank", "initial_balance_cents": 0})
    error_of(response, 422, "invalid_data", "name")


# --- GET /accounts y /accounts/{id} ---


def test_list_returns_only_own_active_accounts_unless_archived_requested(
    client: TestClient, owner_b: User, make_account: Callable[..., Account]
) -> None:
    make_account(owner_b, name="Ajena")
    active = create(client, name="Activa")
    archived = create(client, name="Guardada")
    assert client.post(f"{URL}/{archived['id']}/archive").status_code == 200

    response = client.get(URL)
    assert response.status_code == 200
    assert [a["name"] for a in response.json()["items"]] == [active["name"]]

    with_archived = client.get(URL, params={"include_archived": "true"}).json()
    assert {a["name"] for a in with_archived["items"]} == {"Activa", "Guardada"}


def test_get_one_returns_the_account(client: TestClient) -> None:
    created = create(client)
    response = client.get(f"{URL}/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_account_of_other_owner_is_404_like_a_missing_one(
    client: TestClient, owner_b: User, make_account: Callable[..., Account]
) -> None:
    foreign = client.get(f"{URL}/{make_account(owner_b).id}")
    missing = client.get(f"{URL}/{uuid.uuid4()}")
    error_of(foreign, 404, "not_found", "account_id")
    assert foreign.json() == missing.json()


def test_get_with_malformed_id_is_422(client: TestClient) -> None:
    error_of(client.get(f"{URL}/no-es-un-id"), 422, "invalid_data", "account_id")


# --- PATCH /accounts/{id} ---


def test_patch_renames_and_edits_initial_values_without_movements(
    client: TestClient,
) -> None:
    created = create(client)
    response = client.patch(
        f"{URL}/{created['id']}",
        json={
            "name": "  Banco   Nuevo ",
            "initial_balance_cents": -500000,
            "start_date": "2026-10-01",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["initial_balance_cents"], body["start_date"]) == (
        "Banco Nuevo",
        -500000,
        "2026-10-01",
    )


def test_patch_initial_balance_with_movements_is_409(
    client: TestClient,
    db_session: Session,
    owner_a: User,
    make_movement: Callable[..., Movement],
) -> None:
    created = create(client)
    account = db_session.get(Account, uuid.UUID(created["id"]))
    make_movement(owner_a, MovementType.INCOME, to_account=account)
    response = client.patch(f"{URL}/{created['id']}", json={"initial_balance_cents": 1})
    error_of(response, 409, "conflict", "initial_balance_cents")


@pytest.mark.parametrize("field", ["type", "parent_id"])
def test_patch_cannot_change_type_or_parent(client: TestClient, field: str) -> None:
    created = create(client)
    value = "cash" if field == "type" else str(uuid.uuid4())
    response = client.patch(f"{URL}/{created['id']}", json={field: value})
    error_of(response, 422, "invalid_data", field)


def test_patch_duplicate_name_is_409(client: TestClient) -> None:
    create(client, name="Uno")
    other = create(client, name="Dos")
    response = client.patch(f"{URL}/{other['id']}", json={"name": "UNO"})
    error_of(response, 409, "conflict", "name")


# --- Archivar y desarchivar ---


def test_archive_and_unarchive(client: TestClient) -> None:
    created = create(client)
    archived = client.post(f"{URL}/{created['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["archived"] is True

    restored = client.post(f"{URL}/{created['id']}/unarchive")
    assert restored.status_code == 200
    assert restored.json()["archived"] is False


def test_archive_with_nonzero_balance_is_409(client: TestClient) -> None:
    created = create(client, initial_balance_cents=100)
    error_of(client.post(f"{URL}/{created['id']}/archive"), 409, "conflict", None)


def test_unarchive_active_account_is_409(client: TestClient) -> None:
    created = create(client)
    error_of(client.post(f"{URL}/{created['id']}/unarchive"), 409, "conflict", None)


# --- DELETE /accounts/{id} ---


def test_delete_unused_account_is_204(client: TestClient) -> None:
    created = create(client)
    response = client.delete(f"{URL}/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""
    error_of(client.get(f"{URL}/{created['id']}"), 404, "not_found", "account_id")


def test_delete_account_in_use_is_409(
    client: TestClient,
    db_session: Session,
    owner_a: User,
    make_movement: Callable[..., Movement],
) -> None:
    created = create(client)
    account = db_session.get(Account, uuid.UUID(created["id"]))
    make_movement(owner_a, MovementType.YIELD, to_account=account)
    error_of(client.delete(f"{URL}/{created['id']}"), 409, "conflict", None)


# --- Dependencias reales (las que el cliente de prueba sustituye) ---


def test_real_dependencies_give_system_clock_and_a_session(
    db_engine: Any,
) -> None:
    assert isinstance(deps.get_clock(), SystemClock)

    class FakeApp:
        class state:  # noqa: N801 — imita request.app.state
            engine = db_engine

    class FakeRequest:
        app = FakeApp

    sessions = deps.get_session(FakeRequest())  # type: ignore[arg-type]
    session = next(sessions)
    assert isinstance(session, Session)
    assert session.get_bind() is db_engine
    sessions.close()


def test_account_types_in_api_match_the_domain(client: TestClient) -> None:
    for account_type in AccountType:
        if account_type is AccountType.POCKET:
            continue
        created = create(client, name=f"Cuenta {account_type}", type=account_type)
        assert created["type"] == account_type.value
