"""Errores del negocio: la API los convierte al formato estándar (plan §4.4)."""

from typing import Any, ClassVar

from finanzas.domain.messages import render


class DomainError(Exception):
    """Error con tipo, campo que falló y mensaje del catálogo en español."""

    error_type: ClassVar[str]

    def __init__(
        self,
        code: str,
        *,
        field: str | None = None,
        details: list[dict[str, Any]] | None = None,
        **params: Any,
    ) -> None:
        self.code = code
        self.field = field
        self.details = details or []
        self.message = render(code, **params)
        super().__init__(self.message)


class InvalidData(DomainError):
    """Los datos recibidos no cumplen las reglas (HTTP 422)."""

    error_type = "invalid_data"


class NotFound(DomainError):
    """El recurso no existe o es de otro usuario (HTTP 404, RF-22)."""

    error_type = "not_found"


class Conflict(DomainError):
    """La operación choca con el estado actual (HTTP 409)."""

    error_type = "conflict"
