"""T50: documentación OpenAPI completa y en español (RNF-9, plan §4.2)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from finanzas.config import Settings
from finanzas.main import API_PREFIX, create_app

# Los 23 endpoints de plan §4.2 (archivar y desarchivar cuentan por separado).
ENDPOINTS = {
    ("get", "/health"),
    ("post", "/accounts"),
    ("get", "/accounts"),
    ("get", "/accounts/{account_id}"),
    ("patch", "/accounts/{account_id}"),
    ("post", "/accounts/{account_id}/archive"),
    ("post", "/accounts/{account_id}/unarchive"),
    ("delete", "/accounts/{account_id}"),
    ("post", "/accounts/{account_id}/adjustments"),
    ("post", "/categories"),
    ("get", "/categories"),
    ("patch", "/categories/{category_id}"),
    ("post", "/categories/{category_id}/archive"),
    ("post", "/categories/{category_id}/unarchive"),
    ("delete", "/categories/{category_id}"),
    ("post", "/movements"),
    ("get", "/movements"),
    ("get", "/movements/{movement_id}"),
    ("patch", "/movements/{movement_id}"),
    ("post", "/movements/{movement_id}/void"),
    ("get", "/movements/{movement_id}/history"),
    ("get", "/balances"),
    ("get", "/merchants"),
}

# Textos por defecto de FastAPI, en inglés: no deben quedar en la documentación.
ENGLISH_DEFAULTS = {"Successful Response", "Validation Error"}

ERROR_REF = "#/components/schemas/ErrorOut"


@pytest.fixture(scope="module")
def openapi() -> dict[str, Any]:
    settings = Settings(
        _env_file=None, app_password="clave-de-prueba-12", app_env="local"
    )
    response = TestClient(create_app(settings)).get("/openapi.json")
    assert response.status_code == 200
    spec: dict[str, Any] = response.json()
    return spec


def operations(openapi: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (method, path.removeprefix(API_PREFIX)): operation
        for path, methods in openapi["paths"].items()
        for method, operation in methods.items()
    }


def test_lists_exactly_the_23_endpoints_of_the_plan(openapi: dict[str, Any]) -> None:
    assert set(operations(openapi)) == ENDPOINTS
    assert len(ENDPOINTS) == 23


@pytest.mark.parametrize("endpoint", sorted(ENDPOINTS))
def test_each_endpoint_has_spanish_description_and_error_schema(
    openapi: dict[str, Any], endpoint: tuple[str, str]
) -> None:
    operation = operations(openapi)[endpoint]
    assert operation["summary"].strip()
    assert operation["description"].strip()

    responses = operation["responses"]
    errors = {code: r for code, r in responses.items() if code.startswith(("4", "5"))}
    assert "500" in errors  # todos pueden fallar de forma inesperada
    for code, response in errors.items():
        schema = response["content"]["application/json"]["schema"]
        assert schema == {"$ref": ERROR_REF}, (endpoint, code)
    for response in responses.values():
        assert response["description"] not in ENGLISH_DEFAULTS


@pytest.mark.parametrize("endpoint", sorted(ENDPOINTS - {("get", "/health")}))
def test_protected_endpoints_document_401_and_the_password(
    openapi: dict[str, Any], endpoint: tuple[str, str]
) -> None:
    operation = operations(openapi)[endpoint]
    assert "401" in operation["responses"]
    assert operation["security"] == [{"HTTPBearer": []}]


def test_error_schema_has_the_standard_format(openapi: dict[str, Any]) -> None:
    schemas = openapi["components"]["schemas"]
    body_ref = schemas["ErrorOut"]["properties"]["error"]["$ref"]
    body = schemas[body_ref.rsplit("/", 1)[1]]
    assert set(body["properties"]) == {"type", "field", "message", "details"}
    assert "HTTPValidationError" not in schemas  # el formato de FastAPI no se usa


@pytest.mark.parametrize(
    ("endpoint", "schema_name"),
    [
        (("post", "/accounts"), "AccountCreate"),
        (("post", "/movements"), "MovementCreate"),
        (("patch", "/movements/{movement_id}"), "MovementCorrection"),
        (("post", "/movements/{movement_id}/void"), "VoidRequest"),
        (("post", "/accounts/{account_id}/adjustments"), "AdjustmentRequest"),
    ],
)
def test_request_bodies_show_the_plan_examples(
    openapi: dict[str, Any], endpoint: tuple[str, str], schema_name: str
) -> None:
    schema = openapi["components"]["schemas"][schema_name]
    assert schema["examples"], schema_name
