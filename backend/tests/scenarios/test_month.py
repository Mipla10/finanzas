"""T53: un mes completo por la API con los valores fijos del plan (RNF-1, plan §2.4).

Todo se registra como lo haría la app: cuentas, categorías, M1–M8, la corrección de
M2 y la anulación de M6. Los números esperados son los calculados a mano en §2.4.
"""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from finanzas.domain.dates import FixedClock

API = "/api/v1"


def post(client: TestClient, path: str, body: dict[str, Any], expect: int = 201) -> Any:
    response = client.post(API + path, json=body)
    assert response.status_code == expect, response.text
    return response.json()


@pytest.fixture
def month(client: TestClient, clock: FixedClock) -> dict[str, str]:
    """Registra el mes de §2.4 y devuelve los ids por nombre (A1–A4, M1–M8)."""
    ids: dict[str, str] = {}
    start = "2026-11-01"
    for key, name, kind, parent, initial in [
        ("A1", "Lulo", "bank", None, 150000000),
        ("A2", "Ahorro", "pocket", "A1", 300000000),
        ("A3", "Nequi", "digital_wallet", None, 20000000),
        ("A4", "Efectivo", "cash", None, 5000000),
    ]:
        body = {
            "name": name,
            "type": kind,
            "initial_balance_cents": initial,
            "start_date": start,
            "parent_id": ids[parent] if parent else None,
        }
        ids[key] = post(client, "/accounts", body)["id"]

    for name, kind in [
        ("Salario", "income"),
        ("Domicilios", "expense"),
        ("Comisiones bancarias", "expense"),
        ("Alimentación", "expense"),
    ]:
        ids[name] = post(client, "/categories", {"name": name, "kind": kind})["id"]

    def movement(key: str, **body: Any) -> None:
        ids[key] = post(client, "/movements", body)["movement"]["id"]
        clock.advance(timedelta(minutes=1))  # orden de registro estable

    A1, A2, A3, A4 = ids["A1"], ids["A2"], ids["A3"], ids["A4"]
    movement(
        "M1",
        type="income",
        amount_cents=200000000,
        date="2026-11-01",
        to_account_id=A1,
        category_id=ids["Salario"],
    )
    movement(
        "M2",
        type="expense",
        amount_cents=2300000,  # monto equivocado: se corrige abajo
        date="2026-11-03",
        from_account_id=A3,
        category_id=ids["Domicilios"],
        merchant="Rappi",
    )
    movement(
        "M3",
        type="transfer",
        amount_cents=20000000,
        date="2026-11-05",
        from_account_id=A1,
        to_account_id=A4,
        note="Retiro de cajero",
    )
    movement(
        "M4",
        type="expense",
        amount_cents=700000,
        date="2026-11-05",
        from_account_id=A1,
        category_id=ids["Comisiones bancarias"],
    )
    movement(
        "M5",
        type="transfer",
        amount_cents=50000000,
        date="2026-11-06",
        from_account_id=A1,
        to_account_id=A2,
    )
    movement(
        "M6",
        type="expense",
        amount_cents=8000000,
        date="2026-11-10",
        from_account_id=A4,
        category_id=ids["Alimentación"],
    )
    movement(
        "M7", type="yield", amount_cents=1234567, date="2026-11-20", to_account_id=A2
    )

    correction = client.patch(
        f"{API}/movements/{ids['M2']}", json={"amount_cents": 2500000}
    )
    assert correction.status_code == 200, correction.text
    assert correction.json()["changed"] is True
    post(
        client, f"/movements/{ids['M6']}/void", {"reason": "Registrado dos veces"}, 200
    )

    # M8: el saldo real de Nequi era $ 171.500; el calculado, 17500000.
    adjusted = post(
        client, f"/accounts/{A3}/adjustments", {"real_balance_cents": 17150000}
    )
    ids["M8"] = adjusted["movement"]["id"]
    return ids


def test_rnf_1_balances_match_the_plan_exactly(
    client: TestClient, month: dict[str, str]
) -> None:
    balances = client.get(f"{API}/balances").json()
    by_name = {a["name"]: a["balance_cents"] for a in balances["accounts"]}
    assert by_name == {
        "Lulo": 279300000,
        "Ahorro": 351234567,
        "Nequi": 17150000,
        "Efectivo": 25000000,
    }
    assert balances["groups"] == [
        {"bank_id": month["A1"], "name": "Lulo", "subtotal_cents": 630534567}
    ]
    assert balances["total_cents"] == 672684567


def test_rnf_1_november_list_totals_match_the_plan(
    client: TestClient, month: dict[str, str]
) -> None:
    body = client.get(
        f"{API}/movements",
        params={"date_from": "2026-11-01", "date_to": "2026-11-30"},
    ).json()
    assert body["totals"] == {
        "income_cents": 201234567,
        "yield_cents": 1234567,
        "expense_cents": 3200000,
        "net_cents": 198034567,
    }
    # M6 anulado no aparece; transferencias y ajuste sí, pero no suman.
    listed = {item["id"] for item in body["items"]}
    assert listed == {month[f"M{n}"] for n in (1, 2, 3, 4, 5, 7, 8)}
    assert body["page"]["total_items"] == 7


def test_m2_history_and_m8_adjustment_match_the_plan(
    client: TestClient, month: dict[str, str]
) -> None:
    history = client.get(f"{API}/movements/{month['M2']}/history").json()
    assert [
        (v["version"], v["amount_cents"], v["changed_fields"])
        for v in history["versions"]
    ] == [(1, 2300000, []), (2, 2500000, ["amount_cents"])]
    assert history["voided"] is None

    m8 = client.get(f"{API}/movements/{month['M8']}").json()
    assert (m8["type"], m8["adjustment_direction"], m8["amount_cents"]) == (
        "adjustment",
        "out",
        350000,
    )
    assert m8["date"] == "2026-11-23"

    m6 = client.get(f"{API}/movements/{month['M6']}").json()
    assert (m6["voided"], m6["void_reason"]) == (True, "Registrado dos veces")
