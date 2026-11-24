"""T8: contraseña única en todas las rutas de la API (RNF-4, plan §5.6, DT-11)."""

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from finanzas.api import deps
from finanzas.config import Settings
from finanzas.main import API_PREFIX, create_app

# ASCII obligatorio (RNF-4): las cabeceras HTTP no admiten «ñ» ni tildes.
PASSWORD = "clave-de-prueba-12"

probe = APIRouter()


@probe.get("/probe")
def protected_probe() -> dict[str, str]:
    return {"secret": "visible solo con contraseña"}


def make_client(app_env: str = "production") -> TestClient:
    settings = Settings(_env_file=None, app_password=PASSWORD, app_env=app_env)
    return TestClient(create_app(settings, protected_routers=[probe]))


def bearer(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


def test_without_header_is_rejected() -> None:
    response = make_client().get(f"{API_PREFIX}/probe")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert "contraseña" in response.json()["error"]["message"]  # en español


def test_with_wrong_password_is_rejected() -> None:
    response = make_client().get(f"{API_PREFIX}/probe", headers=bearer("otra-cosa-123"))
    assert response.status_code == 401


@pytest.mark.parametrize(
    "almost",
    [PASSWORD + "x", PASSWORD[:-1], PASSWORD.upper(), PASSWORD[:-1] + "3", ""],
)
def test_almost_right_passwords_are_rejected(almost: str) -> None:
    response = make_client().get(f"{API_PREFIX}/probe", headers=bearer(almost))
    assert response.status_code == 401


def test_other_auth_scheme_is_rejected() -> None:
    response = make_client().get(
        f"{API_PREFIX}/probe", headers={"Authorization": f"Basic {PASSWORD}"}
    )
    assert response.status_code == 401


def test_with_correct_password_is_allowed() -> None:
    response = make_client().get(f"{API_PREFIX}/probe", headers=bearer(PASSWORD))
    assert response.status_code == 200
    assert response.json() == {"secret": "visible solo con contraseña"}


def test_health_stays_public_next_to_protected_routes() -> None:
    assert make_client().get(f"{API_PREFIX}/health").status_code == 200


def test_docs_stay_public_in_local() -> None:
    assert make_client("local").get("/docs").status_code == 200


def test_comparison_uses_constant_time_compare(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[bytes, bytes]] = []
    real = deps.hmac.compare_digest

    def spy(a: bytes, b: bytes) -> bool:
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(deps.hmac, "compare_digest", spy)
    make_client().get(f"{API_PREFIX}/probe", headers=bearer(PASSWORD))
    assert len(calls) == 1


def test_guard_every_api_route_except_health_requires_password() -> None:
    """Guardián: una ruta nueva bajo /api/v1 nace protegida.

    Se revisa el esquema OpenAPI (información pública y estable de FastAPI):
    cada operación protegida declara el requisito de seguridad «Bearer».
    """
    paths = make_client().app.openapi()["paths"]
    assert f"{API_PREFIX}/probe" in paths
    unprotected = [
        f"{method.upper()} {path}"
        for path, operations in paths.items()
        if path.startswith(API_PREFIX) and path != f"{API_PREFIX}/health"
        for method, operation in operations.items()
        if not operation.get("security")
    ]
    assert unprotected == []


def test_health_declares_no_password_requirement() -> None:
    paths = make_client().app.openapi()["paths"]
    assert "security" not in paths[f"{API_PREFIX}/health"]["get"]
