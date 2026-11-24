"""Casos de uso de cuentas (RF-4, RF-5, plan §2.2)."""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from finanzas.db.models import Account
from finanzas.db.repositories import accounts as repo
from finanzas.domain.accounts import AccountType
from finanzas.domain.dates import Clock, validate_start_date
from finanzas.domain.errors import Conflict, InvalidData, NotFound
from finanzas.domain.money import validate_balance
from finanzas.domain.text import ACCOUNT_NAME_MAX, normalize_name


def get_account(
    session: Session, owner_id: uuid.UUID, account_id: uuid.UUID
) -> Account:
    account = repo.get_owned(session, owner_id, account_id)
    if account is None:
        raise NotFound("resource_not_found", field="account_id")
    return account


def list_accounts(
    session: Session, owner_id: uuid.UUID, include_archived: bool = False
) -> list[Account]:
    return repo.list_owned(session, owner_id, include_archived)


def _validate_parent(
    session: Session,
    owner_id: uuid.UUID,
    account_type: AccountType,
    parent_id: uuid.UUID | None,
) -> None:
    """Todo bolsillo cuelga de un banco activo del mismo dueño; nada más tiene padre."""
    if account_type is not AccountType.POCKET:
        if parent_id is not None:
            raise InvalidData("parent_only_for_pocket", field="parent_id")
        return
    if parent_id is None:
        raise InvalidData("required", field="parent_id")
    parent = repo.get_owned(session, owner_id, parent_id)
    if parent is None:  # inexistente o de otro usuario: misma respuesta (RF-22)
        raise NotFound("resource_not_found", field="parent_id")
    if parent.type is not AccountType.BANK:
        raise InvalidData("parent_must_be_bank", field="parent_id")
    if parent.archived_at is not None:
        raise Conflict("parent_archived", field="parent_id")


def create_account(
    session: Session,
    owner_id: uuid.UUID,
    clock: Clock,
    *,
    name: str,
    account_type: AccountType,
    initial_balance_cents: int,
    start_date: date | None = None,
    parent_id: uuid.UUID | None = None,
) -> Account:
    """Crea una cuenta (RF-4). El saldo inicial es el del COMIENZO de start_date."""
    shown, name_key = normalize_name(name, field="name", max_length=ACCOUNT_NAME_MAX)
    balance = validate_balance(initial_balance_cents, field="initial_balance_cents")
    start = validate_start_date(start_date or clock.today(), today=clock.today())
    _validate_parent(session, owner_id, account_type, parent_id)
    if repo.name_taken(session, owner_id, name_key):
        raise Conflict("duplicate_account_name", field="name")

    account = Account(
        id=uuid.uuid4(),
        owner_id=owner_id,
        name=shown,
        name_key=name_key,
        type=account_type,
        parent_id=parent_id,
        initial_balance_cents=balance,
        start_date=start,
        created_at=clock.now(),
    )
    session.add(account)
    session.commit()
    return account
