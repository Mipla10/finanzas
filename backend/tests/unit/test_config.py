"""T3: configuración con contraseña obligatoria (RNF-4, plan §5.6)."""

import pytest
from pydantic import ValidationError

from finanzas.config import Settings

VALID_PASSWORD = "clave-de-prueba-12"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada test parte sin variables de la app (ni del .env real)."""
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)


def load() -> Settings:
    return Settings(_env_file=None)


def test_missing_password_prevents_startup() -> None:
    with pytest.raises(ValidationError):
        load()


def test_password_shorter_than_12_chars_prevents_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_PASSWORD", "corta-11chr")  # 11 caracteres
    with pytest.raises(ValidationError, match="al menos 12 caracteres"):
        load()


@pytest.mark.parametrize(
    "password",
    [
        "contraseña-de-prueba-12",  # ñ
        "clave-de-acción-12",  # tilde
        "clave de prueba 12",  # espacios
    ],
)
def test_password_must_be_printable_ascii_without_spaces(
    monkeypatch: pytest.MonkeyPatch, password: str
) -> None:
    """Viaja en una cabecera HTTP, que solo admite ASCII (RNF-4)."""
    monkeypatch.setenv("APP_PASSWORD", password)
    with pytest.raises(ValidationError, match="ASCII"):
        load()


@pytest.mark.parametrize(
    "password",
    [
        "corta-11chr",  # demasiado corta
        "contraseña-de-prueba-12",  # no ASCII
    ],
)
def test_invalid_password_is_not_shown_in_the_error(
    monkeypatch: pytest.MonkeyPatch, password: str
) -> None:
    """El error de arranque acaba en logs: nunca debe revelar la clave (RNF-4)."""
    monkeypatch.setenv("APP_PASSWORD", password)
    with pytest.raises(ValidationError) as error:
        load()
    assert password not in str(error.value)


def test_password_of_12_chars_is_accepted_and_kept_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_PASSWORD", VALID_PASSWORD)
    settings = load()
    assert settings.app_password.get_secret_value() == VALID_PASSWORD
    assert VALID_PASSWORD not in repr(settings)  # nunca se imprime en logs


def test_app_env_defaults_to_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", VALID_PASSWORD)
    assert load().app_env == "production"


@pytest.mark.parametrize("value", ["local", "production"])
def test_app_env_accepts_local_and_production(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("APP_PASSWORD", VALID_PASSWORD)
    monkeypatch.setenv("APP_ENV", value)
    assert load().app_env == value


def test_app_env_rejects_other_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PASSWORD", VALID_PASSWORD)
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(ValidationError):
        load()


def test_missing_database_url_prevents_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_PASSWORD", VALID_PASSWORD)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="database_url"):
        load()
