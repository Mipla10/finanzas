"""T44: API de categorías (RF-6, plan §4.2)."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from finanzas.db.models import Category, Movement, User
from finanzas.domain.categories import CategoryKind
from finanzas.domain.movements import MovementType

URL = "/api/v1/categories"


def error_of(response: Any, status: int, error_type: str, field: str | None) -> None:
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert (error["type"], error["field"]) == (error_type, field)


def create(client: TestClient, name: str, kind: str = "expense") -> dict[str, Any]:
    response = client.post(URL, json={"name": name, "kind": kind})
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def test_create_returns_201_with_the_category(client: TestClient) -> None:
    body = create(client, "  Mascotas  ")
    uuid.UUID(body.pop("id"))
    assert body == {
        "name": "Mascotas",
        "kind": "expense",
        "archived": False,
        "created_at": "2026-11-23T10:00:00-05:00",
    }


def test_same_name_in_same_kind_is_409_but_other_kind_is_allowed(
    client: TestClient,
) -> None:
    create(client, "Otros Prueba")
    duplicate = client.post(URL, json={"name": "otros prueba", "kind": "expense"})
    error_of(duplicate, 409, "conflict", "name")
    create(client, "Otros Prueba", kind="income")


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"name": "Algo", "kind": "savings"}, "kind"),
        ({"kind": "expense"}, "name"),
        ({"name": "x" * 41, "kind": "expense"}, "name"),
        ({"name": "Algo", "kind": "expense", "parent": "x"}, "parent"),
    ],
)
def test_create_with_invalid_data_is_422(
    client: TestClient, body: dict[str, Any], field: str
) -> None:
    error_of(client.post(URL, json=body), 422, "invalid_data", field)


def test_list_filters_by_kind_and_hides_archived_and_foreign(
    client: TestClient, owner_b: User, make_category: Callable[..., Category]
) -> None:
    make_category(owner_b, name="Ajena")
    gasto = create(client, "Gasto Prueba")
    ingreso = create(client, "Ingreso Prueba", kind="income")
    guardada = create(client, "Guardada Prueba")
    assert client.post(f"{URL}/{guardada['id']}/archive").status_code == 200

    def names(**params: str) -> set[str]:
        response = client.get(URL, params=params)
        assert response.status_code == 200
        return {c["name"] for c in response.json()["items"]}

    assert names() == {"Gasto Prueba", "Ingreso Prueba"}
    assert names(kind="expense") == {gasto["name"]}
    assert names(kind="income") == {ingreso["name"]}
    assert names(include_archived="true") == {
        "Gasto Prueba",
        "Ingreso Prueba",
        "Guardada Prueba",
    }


def test_list_with_unknown_kind_is_422(client: TestClient) -> None:
    error_of(client.get(URL, params={"kind": "otra"}), 422, "invalid_data", "kind")


def test_rename_returns_200_and_rejects_duplicates(client: TestClient) -> None:
    create(client, "Uno Prueba")
    other = create(client, "Dos Prueba")
    renamed = client.patch(f"{URL}/{other['id']}", json={"name": "Tres Prueba"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Tres Prueba"

    duplicate = client.patch(f"{URL}/{other['id']}", json={"name": "UNO PRUEBA"})
    error_of(duplicate, 409, "conflict", "name")


def test_kind_cannot_be_changed(client: TestClient) -> None:
    created = create(client, "Fija Prueba")
    response = client.patch(
        f"{URL}/{created['id']}", json={"name": "Fija Prueba", "kind": "income"}
    )
    error_of(response, 422, "invalid_data", "kind")


def test_rename_requires_name(client: TestClient) -> None:
    created = create(client, "Sin Nombre Prueba")
    error_of(
        client.patch(f"{URL}/{created['id']}", json={}), 422, "invalid_data", "name"
    )


def test_archive_and_unarchive(client: TestClient) -> None:
    created = create(client, "Archivable Prueba")
    archived = client.post(f"{URL}/{created['id']}/archive")
    assert (archived.status_code, archived.json()["archived"]) == (200, True)
    error_of(client.post(f"{URL}/{created['id']}/archive"), 409, "conflict", None)

    restored = client.post(f"{URL}/{created['id']}/unarchive")
    assert (restored.status_code, restored.json()["archived"]) == (200, False)


def test_delete_unused_is_204_and_used_is_409(
    client: TestClient,
    db_session: Session,
    owner_a: User,
    make_movement: Callable[..., Movement],
) -> None:
    unused = create(client, "Borrable Prueba")
    response = client.delete(f"{URL}/{unused['id']}")
    assert (response.status_code, response.content) == (204, b"")

    used = create(client, "Usada Prueba", kind="income")
    category = db_session.get(Category, uuid.UUID(used["id"]))
    assert category is not None and category.kind is CategoryKind.INCOME
    make_movement(owner_a, MovementType.INCOME, category=category)
    error_of(client.delete(f"{URL}/{used['id']}"), 409, "conflict", None)


def test_category_of_other_owner_is_404_like_a_missing_one(
    client: TestClient, owner_b: User, make_category: Callable[..., Category]
) -> None:
    foreign_id = make_category(owner_b).id
    foreign = client.patch(f"{URL}/{foreign_id}", json={"name": "Robada"})
    missing = client.patch(f"{URL}/{uuid.uuid4()}", json={"name": "Robada"})
    error_of(foreign, 404, "not_found", "category_id")
    assert foreign.json() == missing.json()
    error_of(client.delete(f"{URL}/{foreign_id}"), 404, "not_found", "category_id")
