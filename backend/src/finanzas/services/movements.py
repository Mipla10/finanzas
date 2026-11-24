"""Casos de uso de movimientos (RF-7 a RF-11, plan §3.5)."""

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, MovementVersion
from finanzas.db.repositories import accounts as accounts_repo
from finanzas.db.repositories import categories as categories_repo
from finanzas.db.repositories import movements as movements_repo
from finanzas.domain.balances import BalanceWarning
from finanzas.domain.dates import Clock, validate_movement_date
from finanzas.domain.errors import Conflict, InvalidData, NotFound
from finanzas.domain.money import validate_amount
from finanzas.domain.movements import (
    AdjustmentDirection,
    MovementSnapshot,
    MovementType,
    changed_fields,
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
    session: Session,
    owner_id: uuid.UUID,
    account_id: uuid.UUID,
    field: str,
    already_had: frozenset[uuid.UUID] = frozenset(),
) -> Account:
    account = accounts_repo.get_owned(session, owner_id, account_id)
    if account is None:  # inexistente o de otro usuario: misma respuesta (RF-22)
        raise NotFound("resource_not_found", field=field)
    if account.archived_at is not None and account.id not in already_had:
        raise Conflict("account_archived", field=field)
    return account


def _active_category(
    session: Session,
    owner_id: uuid.UUID,
    category_id: uuid.UUID,
    already_had: frozenset[uuid.UUID] = frozenset(),
) -> Category:
    category = categories_repo.get_owned(session, owner_id, category_id)
    if category is None:
        raise NotFound("resource_not_found", field="category_id")
    if category.archived_at is not None and category.id not in already_had:
        raise Conflict("category_archived", field="category_id")
    return category


def _validate(
    session: Session,
    owner_id: uuid.UUID,
    clock: Clock,
    movement_type: MovementType,
    *,
    amount_cents: int,
    on: date,
    from_account_id: uuid.UUID | None,
    to_account_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    already_had: frozenset[uuid.UUID] = frozenset(),
) -> tuple[int, date, list[Account]]:
    """Reglas de un movimiento (plan §3.5): sirven igual para crear y corregir.

    `already_had`: cuentas y categoría que el movimiento ya tenía; al corregir
    se aceptan aunque estén archivadas (RF-19). Lo NUEVO debe estar activo.
    Devuelve el monto y la fecha validados y las cuentas involucradas.
    """
    amount = validate_amount(amount_cents)
    validate_shape(
        movement_type,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        category_id=category_id,
        adjustment_direction=None,
    )
    accounts = [
        _active_account(session, owner_id, account_id, field, already_had)
        for field, account_id in (
            ("from_account_id", from_account_id),
            ("to_account_id", to_account_id),
        )
        if account_id is not None
    ]
    movement_date = validate_movement_date(
        on,
        today=clock.today(),
        account_starts={account.name: account.start_date for account in accounts},
    )
    if category_id is not None:
        category = _active_category(session, owner_id, category_id, already_had)
        validate_category_kind(movement_type, category.kind)
    return amount, movement_date, accounts


def insert_with_first_version(
    session: Session,
    owner_id: uuid.UUID,
    clock: Clock,
    movement_type: MovementType,
    adjustment_direction: AdjustmentDirection | None = None,
    **data: Any,
) -> Movement:
    """Guarda un movimiento YA validado y su versión 1 (RF-20). No confirma."""
    now = clock.now()
    movement = Movement(
        id=uuid.uuid4(),
        owner_id=owner_id,
        type=movement_type,
        adjustment_direction=adjustment_direction,
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
    return movement


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
    amount, movement_date, accounts = _validate(
        session,
        owner_id,
        clock,
        movement_type,
        amount_cents=amount_cents,
        on=on or clock.today(),
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        category_id=category_id,
    )
    shown_merchant, merchant_key = normalize_merchant(merchant)

    movement = insert_with_first_version(
        session,
        owner_id,
        clock,
        movement_type,
        amount_cents=amount,
        date=movement_date,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        category_id=category_id,
        merchant=shown_merchant,
        merchant_key=merchant_key,
        note=normalize_note(note),
    )
    warnings = warnings_for(session, owner_id, accounts)
    session.commit()
    return MovementResult(movement, warnings)


class _Unset:
    """Marca «este dato no se envió» (distinto de None = «bórralo»)."""


UNSET: Any = _Unset()


@dataclass(frozen=True)
class CorrectionResult:
    movement: Movement
    changed: bool  # False: no hubo cambios reales y no se creó versión
    warnings: list[BalanceWarning] = field(default_factory=list)


def _snapshot(movement: Movement) -> MovementSnapshot:
    return MovementSnapshot(
        amount_cents=movement.amount_cents,
        date=movement.date,
        from_account_id=movement.from_account_id,
        to_account_id=movement.to_account_id,
        category_id=movement.category_id,
        merchant=movement.merchant,
        note=movement.note,
    )


def correct_movement(
    session: Session,
    owner_id: uuid.UUID,
    clock: Clock,
    movement_id: uuid.UUID,
    *,
    movement_type: Any = UNSET,
    amount_cents: Any = UNSET,
    on: Any = UNSET,
    from_account_id: Any = UNSET,
    to_account_id: Any = UNSET,
    category_id: Any = UNSET,
    merchant: Any = UNSET,
    note: Any = UNSET,
) -> CorrectionResult:
    """Corrige un movimiento y guarda la versión nueva (RF-19, plan §3.6).

    Sigue siendo el MISMO movimiento; su momento de registro no cambia. Si no
    cambia nada real (p. ej. «rappi» → «RAPPI»), no se crea versión (CL-24).
    """
    movement = movements_repo.get_owned_for_update(session, owner_id, movement_id)
    if movement is None:
        raise NotFound("resource_not_found", field="movement_id")
    if movement.voided_at is not None:
        raise Conflict("movement_voided")  # CL-25
    if movement.type is MovementType.ADJUSTMENT:
        raise Conflict("adjustment_not_correctable")  # CL-18: se anula y reajusta
    if movement_type is not UNSET and movement_type != movement.type:
        raise InvalidData("type_not_changeable", field="type")  # CL-21
    before = _snapshot(movement)

    def pick(given: Any, current: Any) -> Any:
        return current if given is UNSET else given

    after = MovementSnapshot(
        amount_cents=pick(amount_cents, before.amount_cents),
        date=pick(on, before.date),
        from_account_id=pick(from_account_id, before.from_account_id),
        to_account_id=pick(to_account_id, before.to_account_id),
        category_id=pick(category_id, before.category_id),
        merchant=before.merchant
        if merchant is UNSET
        else normalize_merchant(merchant)[0],
        note=before.note if note is UNSET else normalize_note(note),
    )
    changes = changed_fields(before, after)
    if not changes:
        session.commit()  # libera el bloqueo
        return CorrectionResult(movement, changed=False)

    old_accounts = [
        account
        for account_id in (before.from_account_id, before.to_account_id)
        if account_id is not None
        and (account := accounts_repo.get_owned(session, owner_id, account_id))
    ]
    amount, movement_date, new_accounts = _validate(
        session,
        owner_id,
        clock,
        movement.type,
        amount_cents=after.amount_cents,
        on=after.date,
        from_account_id=after.from_account_id,
        to_account_id=after.to_account_id,
        category_id=after.category_id,
        already_had=frozenset(
            item
            for item in (
                before.from_account_id,
                before.to_account_id,
                before.category_id,
            )
            if item is not None
        ),
    )

    now = clock.now()
    data = {
        "amount_cents": amount,
        "date": movement_date,
        "from_account_id": after.from_account_id,
        "to_account_id": after.to_account_id,
        "category_id": after.category_id,
        "merchant": after.merchant,
        "merchant_key": normalize_merchant(after.merchant)[1],
        "note": after.note,
    }
    for name, value in data.items():
        setattr(movement, name, value)
    movement.updated_at = now
    movement.current_version += 1
    session.add(
        MovementVersion(
            id=uuid.uuid4(),
            owner_id=owner_id,
            movement_id=movement.id,
            version_no=movement.current_version,
            changed_fields=changes,
            created_at=now,
            **data,
        )
    )
    # Se revisan las cuentas de antes Y de después (CL-19).
    affected = old_accounts + [a for a in new_accounts if a not in old_accounts]
    warnings = warnings_for(session, owner_id, affected)
    session.commit()
    return CorrectionResult(movement, changed=True, warnings=warnings)
