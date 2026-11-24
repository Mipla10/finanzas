"""Movimientos: tipos y reglas puras (RF-7 a RF-12, plan §2.2).

Regla clave: el dinero SALE de from_account_id y ENTRA a to_account_id,
para todos los tipos. Así el saldo se calcula con una sola fórmula.
"""

import uuid
from dataclasses import dataclass, fields
from datetime import date
from enum import StrEnum

from finanzas.domain.categories import CategoryKind
from finanzas.domain.errors import InvalidData
from finanzas.domain.text import text_key


class MovementType(StrEnum):
    EXPENSE = "expense"  # gasto: sale de una cuenta, con categoría de gasto
    INCOME = "income"  # ingreso: entra a una cuenta, con categoría de ingreso
    TRANSFER = "transfer"  # entre cuentas propias: no es gasto ni ingreso
    YIELD = "yield"  # rendimiento: entra a una cuenta, cuenta como ingreso
    ADJUSTMENT = "adjustment"  # ajuste al saldo real del banco


class AdjustmentDirection(StrEnum):
    IN = "in"  # el saldo real es mayor: entra dinero
    OUT = "out"  # el saldo real es menor: sale dinero


# --- Forma por tipo (tabla de plan §2.2) ---
# Para cada tipo: campos obligatorios. Todo lo demás de SHAPE_FIELDS está prohibido.
# El ajuste depende además de su dirección (in → destino, out → origen).
SHAPE_FIELDS = (
    "from_account_id",
    "to_account_id",
    "category_id",
    "adjustment_direction",
)
_REQUIRED: dict[MovementType, tuple[str, ...]] = {
    MovementType.EXPENSE: ("from_account_id", "category_id"),
    MovementType.INCOME: ("to_account_id", "category_id"),
    MovementType.TRANSFER: ("from_account_id", "to_account_id"),
    MovementType.YIELD: ("to_account_id",),
}
_ADJUSTMENT_REQUIRED: dict[AdjustmentDirection, tuple[str, ...]] = {
    AdjustmentDirection.IN: ("adjustment_direction", "to_account_id"),
    AdjustmentDirection.OUT: ("adjustment_direction", "from_account_id"),
}


def validate_shape(
    movement_type: MovementType,
    *,
    from_account_id: uuid.UUID | None,
    to_account_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    adjustment_direction: AdjustmentDirection | None,
) -> None:
    """Rechaza un movimiento «mal armado» diciendo QUÉ campo falla (RF-7).

    Es la primera defensa (mensaje claro); la BD es la segunda (ck_movement_shape).
    """
    given = {
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "category_id": category_id,
        "adjustment_direction": adjustment_direction,
    }
    if movement_type is MovementType.ADJUSTMENT:
        if adjustment_direction is None:
            raise InvalidData("required", field="adjustment_direction")
        required = _ADJUSTMENT_REQUIRED[adjustment_direction]
    else:
        required = _REQUIRED[movement_type]

    for field in SHAPE_FIELDS:
        if field in required and given[field] is None:
            raise InvalidData("required", field=field)
    for field in SHAPE_FIELDS:
        if field not in required and given[field] is not None:
            raise InvalidData("not_allowed_for_type", field=field)
    if movement_type is MovementType.TRANSFER and from_account_id == to_account_id:
        raise InvalidData("same_account", field="to_account_id")


_CATEGORY_KIND = {
    MovementType.EXPENSE: CategoryKind.EXPENSE,
    MovementType.INCOME: CategoryKind.INCOME,
}


def validate_category_kind(movement_type: MovementType, kind: CategoryKind) -> None:
    """Un gasto lleva categoría de gasto; un ingreso, de ingreso (RF-8, RF-9)."""
    if _CATEGORY_KIND.get(movement_type) is not kind:
        raise InvalidData("category_wrong_kind", field="category_id")


# --- Diff de versiones (RF-19, plan §3.6) ---


@dataclass(frozen=True)
class MovementSnapshot:
    """Los datos de un movimiento que se guardan en cada versión."""

    amount_cents: int
    date: date
    from_account_id: uuid.UUID | None
    to_account_id: uuid.UUID | None
    category_id: uuid.UUID | None
    merchant: str | None
    note: str | None


def changed_fields(old: MovementSnapshot, new: MovementSnapshot) -> list[str]:
    """Campos que cambiaron, en orden fijo. El comercio se compara por su clave:
    «rappi» → «RAPPI» no es un cambio (CL-24)."""
    changes = []
    for field in fields(MovementSnapshot):
        before, after = getattr(old, field.name), getattr(new, field.name)
        if field.name == "merchant":
            before, after = text_key(before), text_key(after)
        if before != after:
            changes.append(field.name)
    return changes
