"""Casos de uso de movimientos (RF-7 a RF-11, plan §3.5)."""

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, MovementVersion
from finanzas.db.repositories import accounts as accounts_repo
from finanzas.db.repositories import categories as categories_repo
from finanzas.domain.balances import BalanceWarning
from finanzas.domain.dates import Clock, validate_movement_date
from finanzas.domain.errors import Conflict, InvalidData, NotFound
from finanzas.domain.money import validate_amount
from finanzas.domain.movements import (
    MovementType,
    validate_category_kind,
    validate_shape,
)
from finanzas.domain.text import normalize_merchant, normalize_note
from finanzas.services.warnings import warnings_for


@dataclass(frozen=True)
class MovementResult:
    """«Recibo» de una operación: el movimiento y los avisos de saldo (RF-14)."""

    movement: Movement
    warnings: list[BalanceWarning] = field(default_factory=list)


def _active_account(
    session: Session, owner_id: uuid.UUID, account_id: uuid.UUID, field: str
) -> Account:
    account = accounts_repo.get_owned(session, owner_id, account_id)
    if account is None:  # inexistente o de otro usuario: misma respuesta (RF-22)
        raise NotFound("resource_not_found", field=field)
    if account.archived_at is not None:
        raise Conflict("account_archived", field=field)
    return account


def _active_category(
    session: Session, owner_id: uuid.UUID, category_id: uuid.UUID
) -> Category:
    category = categories_repo.get_owned(session, owner_id, category_id)
    if category is None:
        raise NotFound("resource_not_found", field="category_id")
    if category.archived_at is not None:
        raise Conflict("category_archived", field="category_id")
    return category


def create_movement(
    session: Session,
    owner_id: uuid.UUID,
    clock: Clock,
    *,
    movement_type: MovementType,
    amount_cents: int,
    on: date | None = None,
    from_account_id: uuid.UUID | None = None,
    to_account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    merchant: str | None = None,
    note: str | None = None,
) -> MovementResult:
    """Registra un gasto, ingreso, transferencia o rendimiento con su versión 1.

    Si algo no cumple las reglas, lanza el error y no guarda nada (RF-22).
    Si deja una cuenta en negativo, se guarda igual y devuelve el aviso (RF-14).
    """
    if movement_type is MovementType.ADJUSTMENT:
        raise InvalidData("adjustment_not_via_movements", field="type")
    amount = validate_amount(amount_cents)
    validate_shape(
        movement_type,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        category_id=category_id,
        adjustment_direction=None,
    )
    accounts = [
        _active_account(session, owner_id, account_id, field)
        for field, account_id in (
            ("from_account_id", from_account_id),
            ("to_account_id", to_account_id),
        )
        if account_id is not None
    ]
    movement_date = validate_movement_date(
        on or clock.today(),
        today=clock.today(),
        account_starts={account.name: account.start_date for account in accounts},
    )
    if category_id is not None:
        category = _active_category(session, owner_id, category_id)
        validate_category_kind(movement_type, category.kind)
    shown_merchant, merchant_key = normalize_merchant(merchant)

    now = clock.now()
    data = {
        "amount_cents": amount,
        "date": movement_date,
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "category_id": category_id,
        "merchant": shown_merchant,
        "merchant_key": merchant_key,
        "note": normalize_note(note),
    }
    movement = Movement(
        id=uuid.uuid4(),
        owner_id=owner_id,
        type=movement_type,
        created_at=now,
        updated_at=now,
        current_version=1,
        **data,
    )
    session.add(movement)
    session.flush()
    session.add(
        MovementVersion(
            id=uuid.uuid4(),
            owner_id=owner_id,
            movement_id=movement.id,
            version_no=1,
            changed_fields=[],
            created_at=now,
            **data,
        )
    )
    warnings = warnings_for(session, owner_id, accounts)
    session.commit()
    return MovementResult(movement, warnings)
