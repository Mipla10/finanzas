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
    # Validación de formato (traducción de los errores de Pydantic, T10)
    "required": "Este campo es obligatorio.",
    "int_type": "Debe ser un número entero.",
    "string_type": "Debe ser un texto.",
    "bool_type": "Debe ser verdadero o falso.",
    "too_short": "El texto debe tener al menos {min_length} caracteres.",
    "gt": "Debe ser mayor que {limit}.",
    "ge": "Debe ser mayor o igual a {limit}.",
    "lt": "Debe ser menor que {limit}.",
    "le": "Debe ser menor o igual a {limit}.",
    "date_invalid": "Debe ser una fecha válida con formato AAAA-MM-DD.",
    "uuid_invalid": "Debe ser un identificador válido.",
    "choice_invalid": "No es uno de los valores permitidos.",
    "extra_field": "Este campo no está permitido.",
    "invalid_json": "El cuerpo de la solicitud no es un JSON válido.",
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
