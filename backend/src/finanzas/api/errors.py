"""Convierte cualquier error al formato estándar (plan §4.4).

{"error": {"type", "field", "message", "details"}}
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
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


async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    # El detalle queda en el log del servidor, nunca en la respuesta.
    logger.exception("Error inesperado", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "internal", render("internal")
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
