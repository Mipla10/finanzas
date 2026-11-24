"""T9/T10: formato estándar de errores, siempre en español (RF-22, RNF-7, plan §4.4)."""

from typing import Any

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

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
