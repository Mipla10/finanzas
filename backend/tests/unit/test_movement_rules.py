"""T19: forma por tipo, clase de categoría y diff de versiones (RF-7 a RF-11, RF-19)."""

import uuid
from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from finanzas.domain.categories import CategoryKind
from finanzas.domain.errors import InvalidData
from finanzas.domain.movements import (
    AdjustmentDirection,
    MovementSnapshot,
    MovementType,
    changed_fields,
    validate_category_kind,
    validate_shape,
)

BANK, CASH, CATEGORY = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
IN, OUT = AdjustmentDirection.IN, AdjustmentDirection.OUT


def shape(movement_type: MovementType, **fields: Any) -> None:
    validate_shape(
        movement_type,
        from_account_id=fields.get("from_account_id"),
        to_account_id=fields.get("to_account_id"),
        category_id=fields.get("category_id"),
        adjustment_direction=fields.get("adjustment_direction"),
    )


# --- Las formas válidas de plan §2.2 ---


@pytest.mark.parametrize(
    ("movement_type", "fields"),
    [
        (MovementType.EXPENSE, {"from_account_id": BANK, "category_id": CATEGORY}),
        (MovementType.INCOME, {"to_account_id": BANK, "category_id": CATEGORY}),
        (MovementType.TRANSFER, {"from_account_id": BANK, "to_account_id": CASH}),
        (MovementType.YIELD, {"to_account_id": BANK}),
        (MovementType.ADJUSTMENT, {"adjustment_direction": IN, "to_account_id": BANK}),
        (
            MovementType.ADJUSTMENT,
            {"adjustment_direction": OUT, "from_account_id": BANK},
        ),
    ],
)
def test_valid_shapes_pass(movement_type: MovementType, fields: dict[str, Any]) -> None:
    shape(movement_type, **fields)


# --- Cada variante inválida falla señalando el campo correcto ---

T = MovementType
INVALID = [
    # (tipo, campos, código esperado, campo esperado)
    (T.EXPENSE, {"category_id": CATEGORY}, "required", "from_account_id"),
    (T.EXPENSE, {"from_account_id": BANK}, "required", "category_id"),
    (
        T.EXPENSE,
        {"from_account_id": BANK, "category_id": CATEGORY, "to_account_id": CASH},
        "not_allowed_for_type",
        "to_account_id",
    ),
    (
        T.EXPENSE,
        {"from_account_id": BANK, "category_id": CATEGORY, "adjustment_direction": IN},
        "not_allowed_for_type",
        "adjustment_direction",
    ),
    (T.INCOME, {"category_id": CATEGORY}, "required", "to_account_id"),
    (T.INCOME, {"to_account_id": BANK}, "required", "category_id"),
    (
        T.INCOME,
        {"to_account_id": BANK, "category_id": CATEGORY, "from_account_id": CASH},
        "not_allowed_for_type",
        "from_account_id",
    ),
    (T.TRANSFER, {"to_account_id": CASH}, "required", "from_account_id"),
    (T.TRANSFER, {"from_account_id": BANK}, "required", "to_account_id"),
    (
        T.TRANSFER,
        {"from_account_id": BANK, "to_account_id": CASH, "category_id": CATEGORY},
        "not_allowed_for_type",
        "category_id",
    ),
    (T.YIELD, {}, "required", "to_account_id"),
    (
        T.YIELD,
        {"to_account_id": BANK, "category_id": CATEGORY},
        "not_allowed_for_type",
        "category_id",
    ),
    (
        T.YIELD,
        {"to_account_id": BANK, "from_account_id": CASH},
        "not_allowed_for_type",
        "from_account_id",
    ),
    (T.ADJUSTMENT, {"to_account_id": BANK}, "required", "adjustment_direction"),
    (
        T.ADJUSTMENT,
        {"adjustment_direction": IN, "from_account_id": BANK},
        "required",
        "to_account_id",
    ),
    (
        T.ADJUSTMENT,
        {"adjustment_direction": OUT, "from_account_id": BANK, "to_account_id": CASH},
        "not_allowed_for_type",
        "to_account_id",
    ),
    (
        T.ADJUSTMENT,
        {"adjustment_direction": IN, "to_account_id": BANK, "category_id": CATEGORY},
        "not_allowed_for_type",
        "category_id",
    ),
]


@pytest.mark.parametrize(("movement_type", "fields", "code", "field"), INVALID)
def test_invalid_shape_fails_with_the_right_field(
    movement_type: MovementType, fields: dict[str, Any], code: str, field: str
) -> None:
    with pytest.raises(InvalidData) as caught:
        shape(movement_type, **fields)
    assert (caught.value.code, caught.value.field) == (code, field)


def test_cl_5_transfer_to_the_same_account_fails() -> None:
    with pytest.raises(InvalidData) as caught:
        shape(MovementType.TRANSFER, from_account_id=BANK, to_account_id=BANK)
    assert (caught.value.code, caught.value.field) == ("same_account", "to_account_id")


# --- Clase de la categoría ---


@pytest.mark.parametrize(
    ("movement_type", "kind"),
    [
        (MovementType.EXPENSE, CategoryKind.EXPENSE),
        (MovementType.INCOME, CategoryKind.INCOME),
    ],
)
def test_category_of_the_right_kind_passes(
    movement_type: MovementType, kind: CategoryKind
) -> None:
    validate_category_kind(movement_type, kind)


@pytest.mark.parametrize(
    ("movement_type", "kind"),
    [
        (MovementType.EXPENSE, CategoryKind.INCOME),
        (MovementType.INCOME, CategoryKind.EXPENSE),
    ],
)
def test_category_of_the_wrong_kind_fails(
    movement_type: MovementType, kind: CategoryKind
) -> None:
    with pytest.raises(InvalidData) as caught:
        validate_category_kind(movement_type, kind)
    assert (caught.value.code, caught.value.field) == (
        "category_wrong_kind",
        "category_id",
    )


# --- Diff de versiones (qué campos cambiaron) ---

BASE = MovementSnapshot(
    amount_cents=2300000,
    date=date(2026, 11, 3),
    from_account_id=BANK,
    to_account_id=None,
    category_id=CATEGORY,
    merchant="rappi",
    note="Almuerzo",
)


def test_identical_snapshots_have_no_changes() -> None:
    assert changed_fields(BASE, replace(BASE)) == []


def test_amount_change_is_detected() -> None:
    assert changed_fields(BASE, replace(BASE, amount_cents=2500000)) == ["amount_cents"]


def test_several_changes_are_listed_in_a_stable_order() -> None:
    new = replace(BASE, note="Cena", from_account_id=CASH, date=date(2026, 11, 4))
    assert changed_fields(BASE, new) == ["date", "from_account_id", "note"]


def test_cl_24_merchant_case_or_spaces_is_not_a_change() -> None:
    assert changed_fields(BASE, replace(BASE, merchant="  RAPPI ")) == []


def test_real_merchant_change_is_detected() -> None:
    assert changed_fields(BASE, replace(BASE, merchant="Tienda Prueba")) == ["merchant"]


def test_removing_the_merchant_is_a_change() -> None:
    assert changed_fields(BASE, replace(BASE, merchant=None)) == ["merchant"]
