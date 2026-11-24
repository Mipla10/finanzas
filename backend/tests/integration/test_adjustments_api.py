"""T48: API de ajuste (RF-12, CL-17, plan §4.3)."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from finanzas.db.models import Account, User
from finanzas.domain.accounts import AccountType


def url(account_id: uuid.UUID) -> str:
    return f"/api/v1/accounts/{account_id}/adjustments"


def error_of(response: Any, status: int, error_type: str, field: str | None) -> None:
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert (error["type"], error["field"]) == (error_type, field)


@pytest.fixture
def nequi(owner_a: User, make_account: Callable[..., Account]) -> Account:
    """Nequi con saldo calculado 17500000, como antes de M8 (plan §2.4)."""
    return make_account(
        owner_a,
        AccountType.DIGITAL_WALLET,
        name="Nequi",
        initial_balance_cents=17500000,
    )


def test_adjusted_is_201_with_the_movement(client: TestClient, nequi: Account) -> None:
    response = client.post(url(nequi.id), json={"real_balance_cents": 17150000})
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"status", "movement", "warnings"}
    assert (body["status"], body["warnings"]) == ("adjusted", [])
    movement = body["movement"]
    assert movement["type"] == "adjustment"
    assert movement["amount_cents"] == 350000
    assert movement["adjustment_direction"] == "out"
    assert movement["date"] == "2026-11-23"
    assert movement["from_account"] == {"id": str(nequi.id), "name": "Nequi"}
    assert movement["to_account"] is None


def test_already_balanced_is_200_without_movement(
    client: TestClient, nequi: Account
) -> None:
    response = client.post(url(nequi.id), json={"real_balance_cents": 17500000})
    assert response.status_code == 200
    assert response.json() == {
        "status": "already_balanced",
        "movement": None,
        "balance_cents": 17500000,
        "warnings": [],
    }


def test_negative_real_balance_creates_adjustment_with_warning(
    client: TestClient, owner_a: User, make_account: Callable[..., Account]
) -> None:
    empty = make_account(owner_a, AccountType.CASH, name="Efectivo Prueba")
    body = client.post(url(empty.id), json={"real_balance_cents": -500000}).json()
    assert body["movement"]["adjustment_direction"] == "out"
    assert body["movement"]["amount_cents"] == 500000
    assert body["warnings"][0]["code"] == "negative_balance"
    assert body["warnings"][0]["balance_cents"] == -500000


def test_cl_17_sending_a_date_is_422(client: TestClient, nequi: Account) -> None:
    response = client.post(
        url(nequi.id), json={"real_balance_cents": 1, "date": "2026-11-20"}
    )
    error_of(response, 422, "invalid_data", "date")


@pytest.mark.parametrize("value", [1715.5, "17150000", None, 2**53])
def test_invalid_real_balance_is_422(
    client: TestClient, nequi: Account, value: Any
) -> None:
    response = client.post(url(nequi.id), json={"real_balance_cents": value})
    error_of(response, 422, "invalid_data", "real_balance_cents")


def test_missing_real_balance_is_422(client: TestClient, nequi: Account) -> None:
    error_of(
        client.post(url(nequi.id), json={}), 422, "invalid_data", "real_balance_cents"
    )


def test_archived_account_is_409(client: TestClient, nequi: Account) -> None:
    client.post(url(nequi.id), json={"real_balance_cents": 0})
    assert client.post(f"/api/v1/accounts/{nequi.id}/archive").status_code == 200
    response = client.post(url(nequi.id), json={"real_balance_cents": 5})
    error_of(response, 409, "conflict", "account_id")


def test_account_of_other_owner_is_404_like_a_missing_one(
    client: TestClient, owner_b: User, make_account: Callable[..., Account]
) -> None:
    foreign = client.post(url(make_account(owner_b).id), json={"real_balance_cents": 1})
    missing = client.post(url(uuid.uuid4()), json={"real_balance_cents": 1})
    error_of(foreign, 404, "not_found", "account_id")
    assert foreign.json() == missing.json()
