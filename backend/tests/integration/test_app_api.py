"""T7: /health siempre público; /docs y /openapi.json solo en local (RNF-4, RNF-9)."""

import pytest
from fastapi.testclient import TestClient

from finanzas.config import Settings
from finanzas.main import create_app

TEST_PASSWORD = "clave-de-prueba-12"


def client_for(app_env: str) -> TestClient:
    settings = Settings(_env_file=None, app_password=TEST_PASSWORD, app_env=app_env)
    return TestClient(create_app(settings))


@pytest.mark.parametrize("app_env", ["local", "production"])
def test_health_is_public_in_every_environment(app_env: str) -> None:
    response = client_for(app_env).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
def test_docs_are_available_in_local(path: str) -> None:
    assert client_for("local").get(path).status_code == 200


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_are_disabled_in_production(path: str) -> None:
    assert client_for("production").get(path).status_code == 404


def test_openapi_in_local_lists_health() -> None:
    paths = client_for("local").get("/openapi.json").json()["paths"]
    assert "/api/v1/health" in paths
