"""Catálogo único de mensajes para el usuario, en español (RNF-7, plan §4.4).

Ningún mensaje se escribe suelto en el código: todos salen de aquí por su
código. Así se pueden revisar juntos y se garantiza que estén en español.
"""

from typing import Any

MESSAGES: dict[str, str] = {
    # Genéricos
    "invalid_value": "El valor no es válido.",
    "resource_not_found": "No se encontró el recurso.",
    "state_conflict": "La operación no es posible en el estado actual.",
    "too_long": "El texto supera el máximo de {max_length} caracteres.",
    # HTTP
    "unauthorized": "Falta la contraseña o es incorrecta.",
    "route_not_found": "La ruta no existe.",
    "method_not_allowed": "El método no está permitido en esta ruta.",
    "http_error": "No se pudo procesar la solicitud.",
    "internal": "Ocurrió un error inesperado. Intenta de nuevo.",
}


def render(code: str, **params: Any) -> str:
    """Texto del mensaje `code` con sus parámetros. Un código desconocido es un bug."""
    return MESSAGES[code].format(**params)
