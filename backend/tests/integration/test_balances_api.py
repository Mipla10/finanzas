"""T49: API de saldos y comercios (RF-13, RF-16, plan §4.3)."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from finanzas.db.models import Account, Movement, User
from finanzas.domain.movements import MovementType


def error_of(response: Any, status: int, error_type: str, field: str | None) -> None:
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert (error["type"], error["field"]) == (error_type, field)


# --- GET /balances ---


def test_balances_return_exactly_the_plan_example_json(
    client: TestClient, month_scenario: dict[str, Account]
) -> None:
    ids = {name: str(account.id) for name, account in month_scenario.items()}
    response = client.get("/api/v1/balances")
    assert response.status_code == 200
    assert response.json() == {
        "accounts": [
            {
                "id": ids["Lulo"],
                "name": "Lulo",
                "type": "bank",
                "parent_id": None,
                "archived": False,
                "balance_cents": 279300000,
            },
            {
                "id": ids["Ahorro"],
                "name": "Ahorro",
                "type": "pocket",
                "parent_id": ids["Lulo"],
                "archived": False,
                "balance_cents": 351234567,
            },
            {
                "id": ids["Nequi"],
                "name": "Nequi",
                "type": "digital_wallet",
                "parent_id": None,
                "archived": False,
                "balance_cents": 17150000,
            },
            {
                "id": ids["Efectivo"],
                "name": "Efectivo",
                "type": "cash",
                "parent_id": None,
                "archived": False,
                "balance_cents": 25000000,
            },
        ],
        "groups": [
            {"bank_id": ids["Lulo"], "name": "Lulo", "subtotal_cents": 630534567}
        ],
        "total_cents": 672684567,
    }


def test_balances_never_include_other_owner(
    client: TestClient, owner_b: User, make_account: Callable[..., Account]
) -> None:
    make_account(owner_b, initial_balance_cents=999)
    assert client.get("/api/v1/balances").json() == {
        "accounts": [],
        "groups": [],
        "total_cents": 0,
    }


# --- GET /merchants ---


@pytest.fixture
def merchants(
    owner_a: User, owner_b: User, make_movement: Callable[..., Movement]
) -> None:
    for name, uses in [("Rappi", 3), ("D1", 2), ("Panadería Prueba", 1)]:
        for _ in range(uses):
            make_movement(owner_a, MovementType.EXPENSE, merchant=name)
    make_movement(owner_b, MovementType.EXPENSE, merchant="Ajeno Prueba")


def test_merchants_most_used_first_and_only_mine(
    client: TestClient, merchants: None
) -> None:
    response = client.get("/api/v1/merchants")
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"merchant": "Rappi", "uses": 3},
            {"merchant": "D1", "uses": 2},
            {"merchant": "Panadería Prueba", "uses": 1},
        ]
    }


def test_merchants_respect_limit(client: TestClient, merchants: None) -> None:
    body = client.get("/api/v1/merchants", params={"limit": 2}).json()
    assert [item["merchant"] for item in body["items"]] == ["Rappi", "D1"]


@pytest.mark.parametrize("limit", [0, 201, "veinte"])
def test_merchants_limit_out_of_range_is_422(client: TestClient, limit: Any) -> None:
    response = client.get("/api/v1/merchants", params={"limit": limit})
    error_of(response, 422, "invalid_data", "limit")
