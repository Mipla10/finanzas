"""T13: tabla movements con su forma por tipo en la BD (RF-7, RNF-5, plan §2.2)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, User
from finanzas.domain.accounts import AccountType
from finanzas.domain.categories import CategoryKind
from finanzas.domain.movements import AdjustmentDirection, MovementType

NOW = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)


@dataclass
class World:
    """Un usuario con dos cuentas y una categoría de cada clase."""

    owner: User
    bank: Account
    cash: Account
    expense_cat: Category
    income_cat: Category


def make_world(session: Session, label: str) -> World:
    owner = User(id=uuid.uuid4(), created_at=NOW)
    session.add(owner)
    session.flush()

    def account(name: str, account_type: AccountType) -> Account:
        return Account(
            id=uuid.uuid4(),
            owner_id=owner.id,
            name=name,
            name_key=name.casefold(),
            type=account_type,
            initial_balance_cents=0,
            start_date=date(2026, 11, 1),
            created_at=NOW,
        )

    def category(name: str, kind: CategoryKind) -> Category:
        return Category(
            id=uuid.uuid4(),
            owner_id=owner.id,
            name=name,
            name_key=name.casefold(),
            kind=kind,
            created_at=NOW,
        )

    world = World(
        owner=owner,
        bank=account(f"Banco {label}", AccountType.BANK),
        cash=account(f"Efectivo {label}", AccountType.CASH),
        expense_cat=category("Comercio X", CategoryKind.EXPENSE),
        income_cat=category("Ingreso Y", CategoryKind.INCOME),
    )
    session.add_all([world.bank, world.cash, world.expense_cat, world.income_cat])
    session.flush()
    return world


def insert_movement(session: Session, owner: User, **fields: Any) -> Movement:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "owner_id": owner.id,
        "amount_cents": 2500000,
        "date": date(2026, 11, 3),
        "created_at": NOW,
        "updated_at": NOW,
        "current_version": 1,
    }
    values.update(fields)
    movement = Movement(**values)
    session.add(movement)
    session.flush()
    return movement


# --- Las 6 formas válidas (tabla de plan §2.2) ---


def valid_shapes(w: World) -> dict[str, dict[str, Any]]:
    return {
        "gasto": {
            "type": MovementType.EXPENSE,
            "from_account_id": w.bank.id,
            "category_id": w.expense_cat.id,
            "merchant": "Comercio X",
            "merchant_key": "comercio x",
            "note": "Nota inventada",
        },
        "ingreso": {
            "type": MovementType.INCOME,
            "to_account_id": w.bank.id,
            "category_id": w.income_cat.id,
        },
        "transferencia": {
            "type": MovementType.TRANSFER,
            "from_account_id": w.bank.id,
            "to_account_id": w.cash.id,
        },
        "rendimiento": {"type": MovementType.YIELD, "to_account_id": w.bank.id},
        "ajuste_entrada": {
            "type": MovementType.ADJUSTMENT,
            "adjustment_direction": AdjustmentDirection.IN,
            "to_account_id": w.cash.id,
        },
        "ajuste_salida": {
            "type": MovementType.ADJUSTMENT,
            "adjustment_direction": AdjustmentDirection.OUT,
            "from_account_id": w.cash.id,
        },
    }


@pytest.mark.parametrize(
    "shape",
    [
        "gasto",
        "ingreso",
        "transferencia",
        "rendimiento",
        "ajuste_entrada",
        "ajuste_salida",
    ],
)
def test_each_valid_shape_is_stored(db_session: Session, shape: str) -> None:
    w = make_world(db_session, "A")
    movement = insert_movement(db_session, w.owner, **valid_shapes(w)[shape])
    assert movement.voided_at is None


# --- Formas inválidas: la BD las rechaza (ck_movement_shape) ---


def invalid_shapes(w: World) -> dict[str, dict[str, Any]]:
    return {
        "gasto sin categoría": {
            "type": MovementType.EXPENSE,
            "from_account_id": w.bank.id,
        },
        "gasto con cuenta destino": {
            "type": MovementType.EXPENSE,
            "from_account_id": w.bank.id,
            "to_account_id": w.cash.id,
            "category_id": w.expense_cat.id,
        },
        "ingreso sin cuenta destino": {
            "type": MovementType.INCOME,
            "category_id": w.income_cat.id,
        },
        "transferencia a la misma cuenta": {
            "type": MovementType.TRANSFER,
            "from_account_id": w.bank.id,
            "to_account_id": w.bank.id,
        },
        "transferencia con categoría": {
            "type": MovementType.TRANSFER,
            "from_account_id": w.bank.id,
            "to_account_id": w.cash.id,
            "category_id": w.expense_cat.id,
        },
        "rendimiento con categoría": {
            "type": MovementType.YIELD,
            "to_account_id": w.bank.id,
            "category_id": w.income_cat.id,
        },
        "ajuste con dos cuentas": {
            "type": MovementType.ADJUSTMENT,
            "adjustment_direction": AdjustmentDirection.IN,
            "from_account_id": w.bank.id,
            "to_account_id": w.cash.id,
        },
        "ajuste sin dirección": {
            "type": MovementType.ADJUSTMENT,
            "to_account_id": w.cash.id,
        },
        "ajuste de entrada que sale": {
            "type": MovementType.ADJUSTMENT,
            "adjustment_direction": AdjustmentDirection.IN,
            "from_account_id": w.cash.id,
        },
        "dirección en un gasto": {
            "type": MovementType.EXPENSE,
            "from_account_id": w.bank.id,
            "category_id": w.expense_cat.id,
            "adjustment_direction": AdjustmentDirection.OUT,
        },
    }


@pytest.mark.parametrize(
    "shape",
    [
        "gasto sin categoría",
        "gasto con cuenta destino",
        "ingreso sin cuenta destino",
        "transferencia a la misma cuenta",
        "transferencia con categoría",
        "rendimiento con categoría",
        "ajuste con dos cuentas",
        "ajuste sin dirección",
        "ajuste de entrada que sale",
        "dirección en un gasto",
    ],
)
def test_invalid_shape_is_rejected(db_session: Session, shape: str) -> None:
    w = make_world(db_session, "A")
    with pytest.raises(IntegrityError, match="ck_movement_shape"):
        insert_movement(db_session, w.owner, **invalid_shapes(w)[shape])


@pytest.mark.parametrize("amount", [0, -500000])
def test_amount_must_be_positive(db_session: Session, amount: int) -> None:
    w = make_world(db_session, "A")
    with pytest.raises(IntegrityError, match="ck_movements_amount_positive"):
        insert_movement(
            db_session, w.owner, amount_cents=amount, **valid_shapes(w)["gasto"]
        )


# --- Aislamiento en la BD: nada de cuentas o categorías ajenas (RNF-5) ---


@pytest.mark.parametrize(
    ("borrowed", "constraint"),
    [
        ("from_account_id", "fk_movements_from_account_owner"),
        ("to_account_id", "fk_movements_to_account_owner"),
        ("category_id", "fk_movements_category_owner"),
    ],
)
def test_resources_of_another_owner_are_rejected(
    db_session: Session, borrowed: str, constraint: str
) -> None:
    mine, theirs = make_world(db_session, "A"), make_world(db_session, "B")
    fields = {
        "from_account_id": {
            "type": MovementType.EXPENSE,
            "from_account_id": theirs.bank.id,
            "category_id": mine.expense_cat.id,
        },
        "to_account_id": {
            "type": MovementType.INCOME,
            "to_account_id": theirs.bank.id,
            "category_id": mine.income_cat.id,
        },
        "category_id": {
            "type": MovementType.EXPENSE,
            "from_account_id": mine.bank.id,
            "category_id": theirs.expense_cat.id,
        },
    }[borrowed]
    with pytest.raises(IntegrityError, match=constraint):
        insert_movement(db_session, mine.owner, **fields)
