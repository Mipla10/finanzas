"""Configuración de la app, leída de variables de entorno o del .env (plan §5.6)."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/finanzas/config.py → raíz del repositorio (donde vive .env).
REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

MIN_PASSWORD_LENGTH = 12


class Settings(BaseSettings):
    """Si falta algo obligatorio o no cumple las reglas, la app no arranca."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_password: SecretStr
    app_env: Literal["local", "production"] = "production"

    @field_validator("app_password")
    @classmethod
    def password_must_be_long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"APP_PASSWORD debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
            )
        return value
