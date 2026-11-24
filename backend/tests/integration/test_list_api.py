"""T46: API para listar movimientos (RF-17, plan §4.3, §5.1)."""

import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, User
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.movements import AdjustmentDirection, MovementType
from finanzas.services.movements import void_movement

URL = "/api/v1/movements"


def error_of(response: Any, status: int, error_type: str, field: str | None) -> None:
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert (error["type"], error["field"]) == (error_type, field)


@pytest.fixture
def cl_38(
    owner_a: User,
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    make_movement: Callable[..., Movement],
) -> dict[str, Any]:
    """CL-38: ingreso 100, rendimiento 10, gasto 30, transferencia 50, ajuste 5."""
    main = make_account(owner_a, name="Principal Prueba")
    other = make_account(owner_a, name="Otra Prueba")
    salary = make_category(owner_a, CategoryKind.INCOME, name="Salario Prueba")
    food = make_category(owner_a, CategoryKind.EXPENSE, name="Comida Prueba")
    movements = {
        "income": make_movement(
            owner_a,
            MovementType.INCOME,
            amount_cents=100,
            on=date(2026, 11, 1),
            to_account=main,
            category=salary,
        ),
        "yield": make_movement(
            owner_a,
            MovementType.YIELD,
            amount_cents=10,
            on=date(2026, 11, 20),
            to_account=main,
        ),
        "expense": make_movement(
            owner_a,
            MovementType.EXPENSE,
            amount_cents=30,
            on=date(2026, 11, 5),
            from_account=main,
            category=food,
            merchant="Comercio X",
        ),
        "transfer": make_movement(
            owner_a,
            MovementType.TRANSFER,
            amount_cents=50,
            on=date(2026, 11, 6),
            from_account=main,
            to_account=other,
        ),
        "adjustment": make_movement(
            owner_a,
            MovementType.ADJUSTMENT,
            amount_cents=5,
            on=date(2026, 11, 23),
            adjustment_direction=AdjustmentDirection.OUT,
            from_account=other,
        ),
    }
    return {"main": main, "other": other, "food": food, **movements}


def test_response_has_items_totals_and_page(
    client: TestClient, cl_38: dict[str, Any]
) -> None:
    response = client.get(URL)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "totals", "page"}
    assert body["totals"] == {
        "income_cents": 110,
        "yield_cents": 10,
        "expense_cents": 30,
        "net_cents": 80,
    }
    assert body["page"] == {"limit": 50, "offset": 0, "total_items": 5}
    # Orden: fecha descendente.
    assert [item["type"] for item in body["items"]] == [
        "adjustment",
        "yield",
        "transfer",
        "expense",
        "income",
    ]
    expense = body["items"][3]
    assert expense["from_account"] == {
        "id": str(cl_38["main"].id),
        "name": "Principal Prueba",
    }
    assert expense["category"]["name"] == "Comida Prueba"
    assert expense["merchant"] == "Comercio X"


def test_repeated_type_parameter_combines_with_or(
    client: TestClient, cl_38: dict[str, Any]
) -> None:
    response = client.get(URL, params=[("type", "expense"), ("type", "income")])
    assert response.status_code == 200
    body = response.json()
    assert {item["type"] for item in body["items"]} == {"expense", "income"}
    assert body["totals"]["net_cents"] == 70  # 100 − 30, sin el rendimiento


def test_filters_by_dates_accounts_and_categories(
    client: TestClient, cl_38: dict[str, Any]
) -> None:
    by_dates = client.get(
        URL, params={"date_from": "2026-11-05", "date_to": "2026-11-06"}
    )
    assert {i["type"] for i in by_dates.json()["items"]} == {"expense", "transfer"}

    by_account = client.get(URL, params={"account_id": str(cl_38["other"].id)})
    assert {i["type"] for i in by_account.json()["items"]} == {"transfer", "adjustment"}

    by_category = client.get(URL, params={"category_id": str(cl_38["food"].id)})
    assert [i["type"] for i in by_category.json()["items"]] == ["expense"]


def test_pagination_keeps_totals_of_the_whole_filter(
    client: TestClient, cl_38: dict[str, Any]
) -> None:
    body = client.get(URL, params={"limit": 2, "offset": 1}).json()
    assert [i["type"] for i in body["items"]] == ["yield", "transfer"]
    assert body["page"] == {"limit": 2, "offset": 1, "total_items": 5}
    assert body["totals"]["income_cents"] == 110


def test_voided_are_listed_only_when_requested(
    client: TestClient,
    cl_38: dict[str, Any],
    db_session: Session,
    owner_a: User,
    clock: FixedClock,
) -> None:
    voided_id = str(cl_38["expense"].id)
    void_movement(db_session, owner_a.id, clock, cl_38["expense"].id)
    default = client.get(URL).json()
    assert voided_id not in {i["id"] for i in default["items"]}

    with_voided = client.get(URL, params={"include_voided": "true"}).json()
    listed = {i["id"]: i for i in with_voided["items"]}
    assert listed[voided_id]["voided"] is True
    assert with_voided["totals"]["expense_cents"] == 0  # los anulados nunca suman


@pytest.mark.parametrize("limit", [0, 201, -1])
def test_limit_out_of_range_is_422(client: TestClient, limit: int) -> None:
    error_of(client.get(URL, params={"limit": limit}), 422, "invalid_data", "limit")


@pytest.mark.parametrize(
    ("params", "status", "error_type", "field"),
    [
        ({"offset": -1}, 422, "invalid_data", "offset"),
        (
            {"date_from": "2026-11-30", "date_to": "2026-11-01"},
            422,
            "invalid_data",
            "date_from",
        ),
        ({"type": "gasto"}, 422, "invalid_data", "type.0"),  # ruta del valor
        ({"account_id": "no-es-un-id"}, 422, "invalid_data", "account_id.0"),
        ({"account_id": str(uuid.uuid4())}, 404, "not_found", "account_id"),
        ({"category_id": str(uuid.uuid4())}, 404, "not_found", "category_id"),
    ],
)
def test_invalid_filters(
    client: TestClient,
    params: dict[str, Any],
    status: int,
    error_type: str,
    field: str,
) -> None:
    error_of(client.get(URL, params=params), status, error_type, field)


def test_never_lists_movements_of_other_owner(
    client: TestClient, owner_b: User, make_movement: Callable[..., Movement]
) -> None:
    make_movement(owner_b, MovementType.EXPENSE)
    body = client.get(URL).json()
    assert body["items"] == []
    assert body["page"]["total_items"] == 0
    assert body["totals"] == {
        "income_cents": 0,
        "yield_cents": 0,
        "expense_cents": 0,
        "net_cents": 0,
    }
