"""T9/T10: formato estándar de errores, siempre en español (RF-22, RNF-7, plan §4.4)."""

from typing import Annotated, Any

import pytest
from fastapi import APIRouter, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from finanzas.config import Settings
from finanzas.domain import messages
from finanzas.domain.errors import Conflict, InvalidData, NotFound
from finanzas.main import API_PREFIX, create_app

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
