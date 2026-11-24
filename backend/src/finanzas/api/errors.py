"""Convierte cualquier error al formato estándar (plan §4.4).

{"error": {"type", "field", "message", "details"}}
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from finanzas.domain.errors import DomainError
from finanzas.domain.messages import render

logger = logging.getLogger(__name__)

DOMAIN_STATUS = {
    "invalid_data": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "not_found": status.HTTP_404_NOT_FOUND,
    "conflict": status.HTTP_409_CONFLICT,
}

# Errores HTTP de FastAPI/Starlette → (tipo, código de mensaje en español).
HTTP_ERRORS = {
    status.HTTP_401_UNAUTHORIZED: ("unauthorized", "unauthorized"),
    status.HTTP_404_NOT_FOUND: ("not_found", "route_not_found"),
    status.HTTP_405_METHOD_NOT_ALLOWED: ("invalid_data", "method_not_allowed"),
}

# Tipo de error de Pydantic → (código del catálogo, {parámetro: clave en ctx}).
# Lo que no esté aquí usa "invalid_value": nunca se muestra texto en inglés.
VALIDATION_MESSAGES: dict[str, tuple[str, dict[str, str]]] = {
    "missing": ("required", {}),
    "int_type": ("int_type", {}),
    "int_parsing": ("int_type", {}),
    "int_from_float": ("int_type", {}),
    "string_type": ("string_type", {}),
    "bool_type": ("bool_type", {}),
    "bool_parsing": ("bool_type", {}),
    "string_too_long": ("too_long", {"max_length": "max_length"}),
    "string_too_short": ("too_short", {"min_length": "min_length"}),
    "greater_than": ("gt", {"limit": "gt"}),
    "greater_than_equal": ("ge", {"limit": "ge"}),
    "less_than": ("lt", {"limit": "lt"}),
    "less_than_equal": ("le", {"limit": "le"}),
    "date_type": ("date_invalid", {}),
    "date_parsing": ("date_invalid", {}),
    "date_from_datetime_parsing": ("date_invalid", {}),
    "date_from_datetime_inexact": ("date_invalid", {}),
    "uuid_type": ("uuid_invalid", {}),
    "uuid_parsing": ("uuid_invalid", {}),
    "literal_error": ("choice_invalid", {}),
    "enum": ("choice_invalid", {}),
    "extra_forbidden": ("extra_field", {}),
    "json_invalid": ("invalid_json", {}),
}

# Primer elemento de `loc` que indica de dónde vino el dato, no el campo.
_LOCATIONS = {"body", "query", "path", "header", "cookie"}


def error_response(
    status_code: int,
    error_type: str,
    message: str,
    field: str | None = None,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = {
        "error": {
            "type": error_type,
            "field": field,
            "message": message,
            "details": details or [],
        }
    }
    return JSONResponse(body, status_code=status_code, headers=headers)


async def handle_domain_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return error_response(
        DOMAIN_STATUS[exc.error_type],
        exc.error_type,
        exc.message,
        field=exc.field,
        details=exc.details,
    )


async def handle_http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    error_type, code = HTTP_ERRORS.get(exc.status_code, ("invalid_data", "http_error"))
    return error_response(
        exc.status_code, error_type, render(code), headers=exc.headers
    )


def translate_validation_error(error: dict[str, Any]) -> dict[str, Any]:
    """Un error de Pydantic → {field, message} en español."""
    code, param_keys = VALIDATION_MESSAGES.get(error["type"], ("invalid_value", {}))
    ctx = error.get("ctx") or {}
    message = render(code, **{name: ctx[key] for name, key in param_keys.items()})

    loc = [str(part) for part in error.get("loc", ())]
    if loc and loc[0] in _LOCATIONS:
        loc = loc[1:]
    field = None if error["type"] == "json_invalid" or not loc else ".".join(loc)
    return {"field": field, "message": message}


async def handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    first, *rest = [translate_validation_error(e) for e in exc.errors()]
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "invalid_data",
        first["message"],
        field=first["field"],
        details=rest,
    )


async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    # El detalle queda en el log del servidor, nunca en la respuesta.
    logger.exception("Error inesperado", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "internal", render("internal")
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
