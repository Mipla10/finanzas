"""T51: aislamiento entre usuarios en cada operación (RNF-5, RF-22, CL-39, plan §8.3).

`owner_a` crea sus datos por la API; luego el cliente pasa a actuar como `owner_b`
y lo intenta todo sobre ellos. Lo ajeno debe responder exactamente igual que un id
que no existe, y nunca aparecer en listados, saldos ni comercios.

(La segunda línea de defensa, la FK compuesta, está en los tests de esquema.)
"""

import json
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from finanzas.api import deps
from finanzas.db.models import User

API = "/api/v1"


def act_as(client: TestClient, user: User) -> None:
    client.app.dependency_overrides[deps.get_owner_id] = lambda: user.id  # type: ignore[attr-defined]


def created(response: Any) -> dict[str, Any]:
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
def ids(client: TestClient, owner_a: User, owner_b: User) -> dict[str, str]:
    """Datos de `owner_a` y recursos propios de `owner_b` para peticiones válidas.

    Al salir, el cliente actúa como `owner_b`.
    """
    lulo = created(
        client.post(
            f"{API}/accounts",
            json={"name": "Banco A", "type": "bank", "initial_balance_cents": 1000000},
        )
    )
    pocket = created(
        client.post(
            f"{API}/accounts",
            json={
                "name": "Bolsillo A",
                "type": "pocket",
                "parent_id": lulo["id"],
                "initial_balance_cents": 0,
            },
        )
    )
    category = created(
        client.post(f"{API}/categories", json={"name": "Comida A", "kind": "expense"})
    )
    movement = created(
        client.post(
            f"{API}/movements",
            json={
                "type": "expense",
                "amount_cents": 250000,
                "from_account_id": lulo["id"],
                "category_id": category["id"],
                "merchant": "Tienda Ajena Prueba",
            },
        )
    )["movement"]

    act_as(client, owner_b)
    own_account = created(
        client.post(
            f"{API}/accounts",
            json={"name": "Banco B", "type": "bank", "initial_balance_cents": 500000},
        )
    )
    own_category = created(
        client.post(f"{API}/categories", json={"name": "Comida B", "kind": "expense"})
    )
    own_movement = created(
        client.post(
            f"{API}/movements",
            json={
                "type": "expense",
                "amount_cents": 1000,
                "from_account_id": own_account["id"],
                "category_id": own_category["id"],
            },
        )
    )["movement"]
    return {
        "a_account": lulo["id"],
        "a_pocket": pocket["id"],
        "a_category": category["id"],
        "a_movement": movement["id"],
        "b_account": own_account["id"],
        "b_category": own_category["id"],
        "b_movement": own_movement["id"],
    }


# (método, ruta, cuerpo, parámetros). `{target}` es el id ajeno bajo prueba; las demás
# claves son recursos propios de `owner_b`, para que la petición sea válida en lo demás.
OPERATIONS: dict[str, tuple[str, str, str, Any, Any]] = {
    # Cuentas
    "leer cuenta": ("a_account", "GET", "/accounts/{target}", None, None),
    "editar cuenta": ("a_account", "PATCH", "/accounts/{target}", {"name": "X"}, None),
    "archivar cuenta": ("a_pocket", "POST", "/accounts/{target}/archive", None, None),
    "desarchivar cuenta": (
        "a_pocket",
        "POST",
        "/accounts/{target}/unarchive",
        None,
        None,
    ),
    "borrar cuenta": ("a_pocket", "DELETE", "/accounts/{target}", None, None),
    "ajustar cuenta": (
        "a_account",
        "POST",
        "/accounts/{target}/adjustments",
        {"real_balance_cents": 0},
        None,
    ),
    "bolsillo en banco ajeno": (
        "a_account",
        "POST",
        "/accounts",
        {
            "name": "Bolsillo B",
            "type": "pocket",
            "parent_id": "{target}",
            "initial_balance_cents": 0,
        },
        None,
    ),
    # Categorías
    "renombrar categoría": (
        "a_category",
        "PATCH",
        "/categories/{target}",
        {"name": "X"},
        None,
    ),
    "archivar categoría": (
        "a_category",
        "POST",
        "/categories/{target}/archive",
        None,
        None,
    ),
    "desarchivar categoría": (
        "a_category",
        "POST",
        "/categories/{target}/unarchive",
        None,
        None,
    ),
    "borrar categoría": ("a_category", "DELETE", "/categories/{target}", None, None),
    # Movimientos
    "leer movimiento": ("a_movement", "GET", "/movements/{target}", None, None),
    "corregir movimiento": (
        "a_movement",
        "PATCH",
        "/movements/{target}",
        {"amount_cents": 1},
        None,
    ),
    "anular movimiento": (
        "a_movement",
        "POST",
        "/movements/{target}/void",
        {"reason": "X"},
        None,
    ),
    "ver historial": ("a_movement", "GET", "/movements/{target}/history", None, None),
    # Usar recursos ajenos dentro de un movimiento propio
    "gasto desde cuenta ajena": (
        "a_account",
        "POST",
        "/movements",
        {
            "type": "expense",
            "amount_cents": 1000,
            "from_account_id": "{target}",
            "category_id": "{b_category}",
        },
        None,
    ),
    "ingreso a cuenta ajena": (
        "a_account",
        "POST",
        "/movements",
        {"type": "yield", "amount_cents": 1000, "to_account_id": "{target}"},
        None,
    ),
    "transferencia a cuenta ajena": (
        "a_account",
        "POST",
        "/movements",
        {
            "type": "transfer",
            "amount_cents": 1000,
            "from_account_id": "{b_account}",
            "to_account_id": "{target}",
        },
        None,
    ),
    "gasto con categoría ajena": (
        "a_category",
        "POST",
        "/movements",
        {
            "type": "expense",
            "amount_cents": 1000,
            "from_account_id": "{b_account}",
            "category_id": "{target}",
        },
        None,
    ),
    "corregir hacia cuenta ajena": (
        "a_account",
        "PATCH",
        "/movements/{b_movement}",
        {"from_account_id": "{target}"},
        None,
    ),
    "corregir hacia categoría ajena": (
        "a_category",
        "PATCH",
        "/movements/{b_movement}",
        {"category_id": "{target}"},
        None,
    ),
    # Filtros del listado con ids ajenos
    "filtrar por cuenta ajena": (
        "a_account",
        "GET",
        "/movements",
        None,
        {"account_id": "{target}"},
    ),
    "filtrar por categoría ajena": (
        "a_category",
        "GET",
        "/movements",
        None,
        {"category_id": "{target}"},
    ),
}


def fill(template: Any, values: dict[str, str]) -> Any:
    if template is None:
        return None
    text = json.dumps(template)
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return json.loads(text)


def send(client: TestClient, operation: str, ids: dict[str, str], target: str) -> Any:
    _, method, path, body, params = OPERATIONS[operation]
    values = {**ids, "target": target}
    return client.request(
        method,
        API + fill(path, values),
        json=fill(body, values),
        params=fill(params, values),
    )


@pytest.mark.parametrize("operation", list(OPERATIONS))
def test_cl_39_foreign_resource_is_404_identical_to_a_missing_one(
    client: TestClient, ids: dict[str, str], operation: str
) -> None:
    foreign = send(client, operation, ids, ids[OPERATIONS[operation][0]])
    missing = send(client, operation, ids, str(uuid.uuid4()))
    assert foreign.status_code == 404, foreign.text
    assert foreign.json()["error"]["type"] == "not_found"
    assert foreign.json() == missing.json()


def test_failed_attempts_leave_owner_a_data_untouched(
    client: TestClient, ids: dict[str, str], owner_a: User
) -> None:
    for operation, (key, *_rest) in OPERATIONS.items():
        send(client, operation, ids, ids[key])

    act_as(client, owner_a)
    account = client.get(f"{API}/accounts/{ids['a_account']}").json()
    assert (account["name"], account["archived"]) == ("Banco A", False)
    pocket = client.get(f"{API}/accounts/{ids['a_pocket']}").json()
    assert pocket["archived"] is False
    names = [c["name"] for c in client.get(f"{API}/categories").json()["items"]]
    assert "Comida A" in names
    movement = client.get(f"{API}/movements/{ids['a_movement']}").json()
    assert movement["amount_cents"] == 250000
    assert movement["voided_at"] is None
    history = client.get(f"{API}/movements/{ids['a_movement']}/history").json()
    assert len(history["versions"]) == 1
    balances = client.get(f"{API}/balances").json()
    assert balances["total_cents"] == 1000000 - 250000


def test_lists_balances_and_merchants_show_nothing_of_owner_a(
    client: TestClient, ids: dict[str, str]
) -> None:
    foreign = {ids[k] for k in ("a_account", "a_pocket", "a_category", "a_movement")}

    def listed(path: str, **params: Any) -> set[str]:
        response = client.get(API + path, params=params)
        assert response.status_code == 200, response.text
        return {item["id"] for item in response.json()["items"]}

    assert listed("/accounts", include_archived=True) == {ids["b_account"]}
    assert not listed("/categories", include_archived=True) & foreign
    assert listed("/movements", include_voided=True) == {ids["b_movement"]}

    totals = client.get(f"{API}/movements").json()["totals"]
    assert totals["expense_cents"] == 1000

    balances = client.get(f"{API}/balances").json()
    assert [a["id"] for a in balances["accounts"]] == [ids["b_account"]]
    assert balances["groups"] == []  # el bolsillo ajeno no forma grupo con nada
    assert balances["total_cents"] == 499000

    merchants = client.get(f"{API}/merchants").json()["items"]
    assert "Tienda Ajena Prueba" not in [m["merchant"] for m in merchants]
