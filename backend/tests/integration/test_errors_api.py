"""T9/T10/T52: formato estándar de errores, siempre en español.

RF-22, RNF-7, plan §4.4.
"""

import ast
import re
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated, Any

import pytest
from fastapi import APIRouter, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import finanzas
from finanzas.api import deps
from finanzas.config import Settings
from finanzas.db.models import Account, Category, Movement, MovementVersion, User
from finanzas.domain import messages
from finanzas.domain.errors import Conflict, InvalidData, NotFound
from finanzas.main import API_PREFIX, create_app
from finanzas.services import movements as movements_service

PASSWORD = "clave-de-prueba-12"
AUTH = {"Authorization": f"Bearer {PASSWORD}"}

probe = APIRouter()


@probe.get("/probe/invalid")
def raise_invalid() -> None:
    raise InvalidData(
        "invalid_value",
        field="amount_cents",
        details=[{"field": "date", "message": messages.render("invalid_value")}],
    )


@probe.get("/probe/not-found")
def raise_not_found() -> None:
    raise NotFound("resource_not_found", field="account_id")


@probe.get("/probe/conflict")
def raise_conflict() -> None:
    raise Conflict("state_conflict")


@probe.get("/probe/boom")
def raise_unexpected() -> None:
    raise RuntimeError("detalle interno secreto: tabla accounts")


class ProbeBody(BaseModel):
    name: str = Field(max_length=5)
    amount: int
    code: str = Field(default="AB", pattern=r"^[A-Z]{2}$")


@probe.post("/probe/validate")
def validate_body(
    body: ProbeBody, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> dict[str, str]:
    return {"ok": body.name}


def make_client() -> TestClient:
    settings = Settings(_env_file=None, app_password=PASSWORD, app_env="production")
    app = create_app(settings, protected_routers=[probe])
    return TestClient(app, raise_server_exceptions=False)


def error_of(response: Any) -> dict[str, Any]:
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"type", "field", "message", "details"}
    return body["error"]


def test_invalid_data_is_422_with_field_and_details() -> None:
    response = make_client().get(f"{API_PREFIX}/probe/invalid", headers=AUTH)
    assert response.status_code == 422
    assert error_of(response) == {
        "type": "invalid_data",
        "field": "amount_cents",
        "message": messages.render("invalid_value"),
        "details": [{"field": "date", "message": messages.render("invalid_value")}],
    }


def test_not_found_is_404() -> None:
    response = make_client().get(f"{API_PREFIX}/probe/not-found", headers=AUTH)
    assert response.status_code == 404
    assert error_of(response) == {
        "type": "not_found",
        "field": "account_id",
        "message": messages.render("resource_not_found"),
        "details": [],
    }


def test_conflict_is_409_without_field() -> None:
    response = make_client().get(f"{API_PREFIX}/probe/conflict", headers=AUTH)
    assert response.status_code == 409
    error = error_of(response)
    assert error["type"] == "conflict"
    assert error["field"] is None
    assert error["message"] == messages.render("state_conflict")


def test_unauthorized_uses_standard_format_and_keeps_header() -> None:
    response = make_client().get(f"{API_PREFIX}/probe/conflict")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    error = error_of(response)
    assert error["type"] == "unauthorized"
    assert error["message"] == messages.render("unauthorized")


@pytest.mark.parametrize("path", ["/no-existe", f"{API_PREFIX}/no-existe"])
def test_unknown_route_is_404_in_spanish(path: str) -> None:
    response = make_client().get(path, headers=AUTH)
    assert response.status_code == 404
    error = error_of(response)
    assert error["type"] == "not_found"
    assert error["message"] == messages.render("route_not_found")


def test_wrong_method_is_405_in_spanish() -> None:
    response = make_client().post(f"{API_PREFIX}/health")
    assert response.status_code == 405
    assert error_of(response)["message"] == messages.render("method_not_allowed")


def test_unexpected_failure_is_500_without_internal_details() -> None:
    response = make_client().get(f"{API_PREFIX}/probe/boom", headers=AUTH)
    assert response.status_code == 500
    error = error_of(response)
    assert error == {
        "type": "internal",
        "field": None,
        "message": messages.render("internal"),
        "details": [],
    }
    assert "secreto" not in response.text


# --- T10: errores de validación traducidos (RF-22, RNF-7, riesgo R-3) ---

ENGLISH_HINTS = ("Field required", "Input should", "String should", "valid integer")
VALIDATE = f"{API_PREFIX}/probe/validate"


def validation_error(response: Any) -> dict[str, Any]:
    assert response.status_code == 422
    error = error_of(response)
    assert error["type"] == "invalid_data"
    for text in [error["message"]] + [d["message"] for d in error["details"]]:
        assert not any(hint in text for hint in ENGLISH_HINTS), text
    return error


def test_missing_fields_point_to_first_field_and_list_the_rest() -> None:
    response = make_client().post(VALIDATE, json={}, headers=AUTH)
    error = validation_error(response)
    assert error["field"] == "name"
    assert error["message"] == messages.render("required")
    assert error["details"] == [
        {"field": "amount", "message": messages.render("required")}
    ]


def test_wrong_type_says_what_was_expected() -> None:
    response = make_client().post(
        VALIDATE, json={"name": "ok", "amount": "abc"}, headers=AUTH
    )
    error = validation_error(response)
    assert error["field"] == "amount"
    assert error["message"] == messages.render("int_type")


def test_text_too_long_mentions_the_limit() -> None:
    response = make_client().post(
        VALIDATE, json={"name": "demasiado", "amount": 1}, headers=AUTH
    )
    error = validation_error(response)
    assert error["field"] == "name"
    assert error["message"] == messages.render("too_long", max_length=5)


@pytest.mark.parametrize(("limit", "code", "bound"), [(0, "ge", 1), (201, "le", 200)])
def test_query_param_out_of_range(limit: int, code: str, bound: int) -> None:
    response = make_client().post(
        f"{VALIDATE}?limit={limit}", json={"name": "ok", "amount": 1}, headers=AUTH
    )
    error = validation_error(response)
    assert error["field"] == "limit"
    assert error["message"] == messages.render(code, limit=bound)


def test_malformed_json_has_no_field() -> None:
    response = make_client().post(
        VALIDATE,
        content=b'{"name": ',
        headers={**AUTH, "Content-Type": "application/json"},
    )
    error = validation_error(response)
    assert error["field"] is None
    assert error["message"] == messages.render("invalid_json")


def test_untranslated_error_falls_back_to_generic_spanish() -> None:
    response = make_client().post(
        VALIDATE, json={"name": "ok", "amount": 1, "code": "x"}, headers=AUTH
    )
    error = validation_error(response)
    assert error["field"] == "code"
    assert error["message"] == messages.render("invalid_value")


@pytest.mark.parametrize(
    ("loc", "field"),
    [((), None), (("items", 0, "name"), "items.0.name"), (("body",), None)],
)
def test_field_path_without_location_prefix(loc: tuple[Any, ...], field: Any) -> None:
    from finanzas.api.errors import translate_validation_error

    translated = translate_validation_error({"type": "missing", "loc": loc})
    assert translated == {"field": field, "message": messages.render("required")}


# --- T52: sin cambios parciales y todo en español (RF-22, RNF-7, plan §4.4) ---


def test_failure_between_movement_and_version_leaves_no_rows(
    client: TestClient,
    db_session: Session,
    owner_a: User,
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = make_account(owner_a, initial_balance_cents=100000)
    category = make_category(owner_a)

    def per_request_session() -> Iterator[Session]:
        # Como en producción: una sesión por petición que se cierra sin confirmar
        # si algo falla (aquí, sobre un savepoint de la transacción del test).
        with Session(
            bind=db_session.connection(), join_transaction_mode="create_savepoint"
        ) as session:
            yield session

    def count(model: Any) -> int:
        query = select(func.count()).select_from(model)
        return db_session.scalar(query.where(model.owner_id == owner_a.id)) or 0

    movements_seen: list[int] = []

    def failing_version(**_: Any) -> None:
        movements_seen.append(count(Movement))  # el movimiento ya se insertó
        raise RuntimeError("fallo simulado antes de guardar la versión")

    client.app.dependency_overrides[deps.get_session] = per_request_session  # type: ignore[attr-defined]
    monkeypatch.setattr(movements_service, "MovementVersion", failing_version)

    response = client.post(
        f"{API_PREFIX}/movements",
        json={
            "type": "expense",
            "amount_cents": 2500,
            "from_account_id": str(account.id),
            "category_id": str(category.id),
        },
    )

    assert response.status_code == 500
    assert error_of(response)["message"] == messages.render("internal")
    assert movements_seen == [1]
    assert (count(Movement), count(MovementVersion)) == (0, 0)


ENGLISH_WORDS = {
    "the", "is", "must", "should", "field", "value", "invalid", "required",
    "not", "found", "cannot", "account", "amount", "date", "balance", "please",
}  # fmt: skip


@pytest.mark.parametrize("code", sorted(messages.MESSAGES))
def test_every_catalog_message_is_spanish(code: str) -> None:
    text = messages.MESSAGES[code]
    without_params = re.sub(r"\{\w+\}", "", text)  # {account} no es texto visible
    words = set(re.findall(r"[a-záéíóúñü]+", without_params.lower()))
    assert not words & ENGLISH_WORDS, (code, text)
    assert text[0].isupper() and text.endswith("."), (code, text)


def test_every_literal_code_in_the_source_exists_in_the_catalog() -> None:
    source = Path(finanzas.__file__).parent
    raisers = {"InvalidData", "NotFound", "Conflict", "render"}
    unknown = []
    for path in source.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and node.args):
                continue
            name = getattr(node.func, "id", getattr(node.func, "attr", None))
            first = node.args[0]
            if (
                name in raisers
                and isinstance(first, ast.Constant)
                and first.value not in messages.MESSAGES
            ):
                unknown.append((path.name, node.lineno, first.value))
    assert unknown == []


def catalog_codes_of(message: str) -> set[str]:
    """Códigos del catálogo cuyo texto (con parámetros) produce `message`."""
    codes = set()
    for code, template in messages.MESSAGES.items():
        pattern = re.sub(r"\\\{\w+\\\}", ".+", re.escape(template))
        if re.fullmatch(pattern, message):
            codes.add(code)
    return codes


# Códigos que la API real no puede producir: otra validación los atrapa antes o son
# genéricos de respaldo. Sus textos se prueban con las rutas de prueba de T9/T10.
NOT_REACHABLE_VIA_API = {
    "invalid_value": "respaldo para errores de Pydantic sin traducción",
    "state_conflict": "conflicto genérico, sin uso en los servicios",
    "amount_not_integer": "el esquema estricto responde antes con int_type",
    "gt": "la API solo usa límites ge/le",
    "lt": "la API solo usa límites ge/le",
    "too_short": "la API no exige longitudes mínimas en el esquema",
    "http_error": "respaldo para códigos HTTP sin traducción",
}


def test_walk_every_error_and_warning_through_the_api(client: TestClient) -> None:
    """Provoca cada error y advertencia posibles por la API real (hoy: 23/11/2026).

    Cada mensaje recibido debe salir del catálogo en español, y entre todos deben
    cubrir el catálogo completo, salvo lo inalcanzable documentado arriba.
    """
    seen: set[str] = set()
    v1 = API_PREFIX

    def call(method: str, path: str, expect: int, **kwargs: Any) -> Any:
        response = client.request(method, v1 + path, **kwargs)
        assert response.status_code == expect, (method, path, response.text)
        body = response.json() if response.content else {}
        texts = []
        if "error" in body:
            texts.append(body["error"]["message"])
            texts += [d["message"] for d in body["error"]["details"]]
        texts += [w["message"] for w in body.get("warnings", [])]
        for text in texts:
            codes = catalog_codes_of(text)
            assert codes, f"mensaje fuera del catálogo: {text!r}"
            seen.update(codes)
        return body

    def account(name: str, kind: str = "bank", expect: int = 201, **extra: Any) -> Any:
        data = {"name": name, "type": kind, "initial_balance_cents": 0, **extra}
        return call("POST", "/accounts", expect, json=data)

    def movement(expect: int, **data: Any) -> Any:
        return call("POST", "/movements", expect, json={"amount_cents": 1000, **data})

    start = {"start_date": "2026-11-01"}
    bank = account("Banco", initial_balance_cents=100000, **start)["id"]
    account("Bolsillo", "pocket", parent_id=bank)
    cash = account("Caja", "cash", **start)["id"]
    food = call("POST", "/categories", 201, json={"name": "Comida", "kind": "expense"})
    salary = call("POST", "/categories", 201, json={"name": "Sueldo", "kind": "income"})
    food, salary = food["id"], salary["id"]
    spent = movement(201, type="expense", from_account_id=bank, category_id=food)
    spent = spent["movement"]["id"]

    # Cuentas
    call("GET", f"/accounts/{uuid.uuid4()}", 404)
    account("x" * 61, expect=422)
    account("Futura", expect=422, start_date="2026-12-01")
    account("banco", expect=409)
    account("Con padre", expect=422, parent_id=bank)
    account("Bolsillo caja", "pocket", expect=422, parent_id=cash)
    closed = account("Banco cerrado")["id"]
    call("POST", f"/accounts/{closed}/archive", 200)
    call("POST", f"/accounts/{closed}/archive", 409)
    account("Bolsillo cerrado", "pocket", expect=409, parent_id=closed)
    call("POST", f"/accounts/{cash}/unarchive", 409)
    call("PATCH", f"/accounts/{bank}", 409, json={"initial_balance_cents": 1})
    full = account("Llena", "digital_wallet", initial_balance_cents=5000)["id"]
    call("POST", f"/accounts/{full}/archive", 409)
    parent = account("Banco padre")["id"]
    account("Bolsillo activo", "pocket", parent_id=parent)
    call("POST", f"/accounts/{parent}/archive", 409)
    call("DELETE", f"/accounts/{parent}", 409)

    # Categorías
    call("POST", "/categories", 409, json={"name": "comida", "kind": "expense"})
    call("DELETE", f"/categories/{food}", 409)
    old = call("POST", "/categories", 201, json={"name": "Vieja", "kind": "expense"})
    call("POST", f"/categories/{old['id']}/archive", 200)

    # Movimientos
    expense = {"type": "expense", "from_account_id": bank, "category_id": food}
    movement(422, **{**expense, "amount_cents": 0})
    movement(422, **{**expense, "amount_cents": 2**53})
    movement(422, **expense, date="2026-11-24")
    movement(422, **expense, date="2026-10-31")
    movement(422, type="expense", from_account_id=bank)
    movement(422, **{**expense, "category_id": salary})
    movement(422, type="yield", to_account_id=bank, category_id=food)
    movement(422, type="transfer", from_account_id=bank, to_account_id=bank)
    movement(422, type="adjustment", from_account_id=bank)
    movement(409, **{**expense, "from_account_id": closed})
    movement(409, **{**expense, "category_id": old["id"]})
    call("PATCH", f"/movements/{spent}", 422, json={"type": "income"})
    call("GET", "/movements", 422, params={"date_from": "2026-11-20", "date_to": "1"})
    call(
        "GET",
        "/movements",
        422,
        params={"date_from": "2026-11-20", "date_to": "2026-11-10"},
    )
    adjusted = call(
        "POST", f"/accounts/{cash}/adjustments", 201, json={"real_balance_cents": 10}
    )
    call("PATCH", f"/movements/{adjusted['movement']['id']}", 409, json={"note": "x"})
    call("POST", f"/movements/{spent}/void", 200)
    call("POST", f"/movements/{spent}/void", 409)
    call("PATCH", f"/movements/{spent}", 409, json={"note": "x"})

    # Advertencias: saldo negativo y cuenta archivada con saldo distinto de cero
    movement(201, **{**expense, "from_account_id": cash, "amount_cents": 50})
    wallet = account("Billetera", "digital_wallet")["id"]
    movement(201, type="yield", to_account_id=wallet)
    out = movement(201, type="transfer", from_account_id=wallet, to_account_id=bank)
    call("POST", f"/accounts/{wallet}/archive", 200)
    call("POST", f"/movements/{out['movement']['id']}/void", 200)
    call("DELETE", f"/accounts/{cash}", 409)  # ya se usó (sin bolsillos)

    # Formato y HTTP
    call("POST", "/accounts", 422, json={"name": 1, "type": "bank"})
    call("POST", "/accounts", 422, json={"name": "A", "type": "otro", "extra": 1})
    movement(422, **{**expense, "amount_cents": "1000"})
    call("GET", "/movements", 422, params={"include_voided": "quizás", "limit": 0})
    call("GET", "/movements", 422, params={"limit": 999, "account_id": "no-es-id"})
    call(
        "POST",
        "/movements",
        422,
        content="{",
        headers={"Content-Type": "application/json"},
    )
    call("GET", "/no-existe", 404)
    call("DELETE", "/balances", 405)
    call("GET", "/balances", 401, headers={"Authorization": "Bearer otra"})
    call("GET", "/accounts", 200)  # sin errores: no aporta mensajes

    expected = set(messages.MESSAGES) - set(NOT_REACHABLE_VIA_API) - {"internal"}
    assert seen >= expected, sorted(expected - seen)
