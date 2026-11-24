"""Formato estándar de error para la documentación (plan §4.4).

Los handlers de api/errors.py producen exactamente esta forma.
"""

from typing import Any, Literal

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    field: str | None
    message: str


class ErrorBody(BaseModel):
    type: Literal["unauthorized", "not_found", "conflict", "invalid_data", "internal"]
    field: str | None  # ruta del campo que falló, o null
    message: str  # en español
    details: list[ErrorDetail]  # errores adicionales si falla más de un campo


class ErrorOut(BaseModel):
    error: ErrorBody

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": {
                        "type": "invalid_data",
                        "field": "date",
                        "message": "No se admiten fechas futuras.",
                        "details": [],
                    }
                }
            ]
        }
    }


_DESCRIPTIONS = {
    401: "Falta la contraseña o es incorrecta.",
    404: "El recurso no existe o es de otro usuario.",
    409: "La operación choca con el estado actual.",
    422: "Datos inválidos.",
    500: "Error inesperado.",
}


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """Errores que documenta una ruta, todos con el formato estándar."""
    return {
        code: {"model": ErrorOut, "description": _DESCRIPTIONS[code]} for code in codes
    }
