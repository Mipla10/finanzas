"""Configuración de la app, leída de variables de entorno o del .env (plan §5.6)."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/finanzas/config.py → raíz del repositorio (donde vive .env).
REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

MIN_PASSWORD_LENGTH = 12


_ENV_CONFIG = SettingsConfigDict(
    env_file=REPO_ROOT_ENV_FILE,
    env_file_encoding="utf-8",
    extra="ignore",
)


class DatabaseSettings(BaseSettings):
    """Solo la conexión a la BD: lo único que necesitan las migraciones."""

    model_config = _ENV_CONFIG

    database_url: str


class Settings(DatabaseSettings):
    """Si falta algo obligatorio o no cumple las reglas, la app no arranca.

    Incluye database_url (heredado): la app siembra el usuario al arrancar.
    """

    app_password: SecretStr
    app_env: Literal["local", "production"] = "production"

    @field_validator("app_password")
    @classmethod
    def password_must_be_valid(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"APP_PASSWORD debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
            )
        # Viaja en una cabecera HTTP: solo ASCII imprimible, sin espacios (! … ~).
        if not all("!" <= char <= "~" for char in password):
            raise ValueError(
                "APP_PASSWORD solo puede tener caracteres ASCII imprimibles, "
                "sin ñ, tildes ni espacios."
            )
        return value
