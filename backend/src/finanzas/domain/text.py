"""Normalización de textos (RF-13, plan §5.2 y §5.3).

- Forma mostrada: sin espacios en los extremos y con los internos colapsados.
- Clave: la forma mostrada en casefold; sirve para comparar y agrupar.
- Las tildes se conservan: «Éxito» y «Exito» son distintos.
- Las longitudes se miden después de limpiar.
"""

from finanzas.domain.errors import InvalidData

ACCOUNT_NAME_MAX = 60
CATEGORY_NAME_MAX = 40
MERCHANT_MAX = 80
NOTE_MAX = 500
VOID_REASON_MAX = 200


def display_form(value: str | None) -> str | None:
    """«  Mc   Donalds » → «Mc Donalds». Vacío o solo espacios → None."""
    if value is None:
        return None
    return " ".join(value.split()) or None


def text_key(value: str | None) -> str | None:
    """«  RAPPI » → «rappi». Vacío → None."""
    shown = display_form(value)
    return shown.casefold() if shown else None


def _check_length(value: str, field: str, max_length: int) -> str:
    if len(value) > max_length:
        raise InvalidData("too_long", field=field, max_length=max_length)
    return value


def normalize_name(value: str | None, field: str, max_length: int) -> tuple[str, str]:
    """Nombre obligatorio (cuenta o categoría) → (forma mostrada, clave)."""
    shown = display_form(value)
    if shown is None:
        raise InvalidData("required", field=field)
    _check_length(shown, field, max_length)
    return shown, shown.casefold()


def normalize_merchant(value: str | None) -> tuple[str | None, str | None]:
    """Comercio opcional → (forma mostrada, clave) o (None, None)."""
    shown = display_form(value)
    if shown is None:
        return None, None
    _check_length(shown, "merchant", MERCHANT_MAX)
    return shown, shown.casefold()


def _normalize_free_text(value: str | None, field: str, max_length: int) -> str | None:
    """Texto libre opcional: recorta los extremos y conserva los saltos internos."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return _check_length(trimmed, field, max_length)


def normalize_note(value: str | None) -> str | None:
    return _normalize_free_text(value, "note", NOTE_MAX)


def normalize_void_reason(value: str | None) -> str | None:
    return _normalize_free_text(value, "reason", VOID_REASON_MAX)
