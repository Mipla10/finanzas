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
    # Dinero (RF-1)
    "amount_not_integer": "Debe ser un número entero de centavos.",
    "amount_not_positive": "El monto debe ser mayor que cero.",
    "amount_too_large": "El valor supera el límite técnico de {max} centavos.",
    # Fechas (RF-2)
    "date_in_future": "No se admiten fechas futuras.",
    "date_before_account_start": (
        "La fecha es anterior al inicio de la cuenta {account} ({start})."
    ),
    "start_date_in_future": "La fecha de inicio no puede ser futura.",
    # Cuentas (RF-4, RF-5)
    "duplicate_account_name": "Ya tienes una cuenta con ese nombre.",
    "parent_only_for_pocket": "Solo un bolsillo puede tener cuenta padre.",
    "parent_must_be_bank": "La cuenta padre de un bolsillo debe ser un banco.",
    "parent_archived": "La cuenta padre está archivada.",
    "account_has_movements": (
        "La cuenta ya tiene movimientos: corrige su saldo con un ajuste."
    ),
    "account_balance_not_zero": "Solo se puede archivar una cuenta con saldo en cero.",
    "account_has_active_pockets": "Primero archiva sus bolsillos activos: {pockets}.",
    "already_archived": "Ya está archivada.",
    "not_archived": "No está archivada.",
    "account_in_use": "La cuenta ya se usó: archívala en vez de borrarla.",
    "account_has_pockets": "La cuenta tiene bolsillos: no se puede borrar.",
    # Movimientos (RF-7 a RF-11)
    "not_allowed_for_type": "Este campo no aplica a este tipo de movimiento.",
    "same_account": "La cuenta de destino debe ser distinta de la de origen.",
    "category_wrong_kind": "La categoría no es de la clase correcta para este tipo.",
    # Advertencias de saldo (RF-14): avisan, nunca bloquean
    "negative_balance": "La cuenta {account} quedó con saldo negativo.",
    "archived_nonzero_balance": (
        "La cuenta archivada {account} quedó con saldo distinto de cero."
    ),
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
