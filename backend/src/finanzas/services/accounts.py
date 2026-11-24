"""Casos de uso de cuentas (RF-4, RF-5, plan §2.2)."""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from finanzas.db.models import Account
from finanzas.db.repositories import accounts as repo
from finanzas.db.repositories.balances import balances_for_owner
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


def update_account(
    session: Session,
    owner_id: uuid.UUID,
    clock: Clock,
    account_id: uuid.UUID,
    *,
    name: str | None = None,
    initial_balance_cents: int | None = None,
    start_date: date | None = None,
) -> Account:
    """Edita una cuenta (RF-5). None = no cambiar ese dato.

    El tipo y la cuenta padre nunca cambian (no son parámetros). El saldo y la
    fecha iniciales solo cambian si no hay movimientos: si no, se usa un ajuste.
    """
    account = get_account(session, owner_id, account_id)

    if name is not None:
        shown, name_key = normalize_name(
            name, field="name", max_length=ACCOUNT_NAME_MAX
        )
        if repo.name_taken(session, owner_id, name_key, exclude_id=account.id):
            raise Conflict("duplicate_account_name", field="name")
        account.name, account.name_key = shown, name_key

    initial_values = {
        "initial_balance_cents": initial_balance_cents,
        "start_date": start_date,
    }
    changing = [field for field, value in initial_values.items() if value is not None]
    if changing and repo.used_by_movements(session, owner_id, account.id):
        raise Conflict("account_has_movements", field=changing[0])
    if initial_balance_cents is not None:
        account.initial_balance_cents = validate_balance(
            initial_balance_cents, field="initial_balance_cents"
        )
    if start_date is not None:
        account.start_date = validate_start_date(start_date, today=clock.today())

    session.commit()
    return account


def archive_account(
    session: Session, owner_id: uuid.UUID, clock: Clock, account_id: uuid.UUID
) -> Account:
    """Archiva (RF-5): ya no admite movimientos nuevos; su historial queda intacto.

    Solo con saldo en cero (CL-28) y sin bolsillos activos (CL-29).
    """
    account = get_account(session, owner_id, account_id)
    if account.archived_at is not None:
        raise Conflict("already_archived")
    pockets = repo.active_pockets(session, owner_id, account.id)
    if pockets:
        names = ", ".join(pocket.name for pocket in pockets)
        raise Conflict("account_has_active_pockets", pockets=names)
    if balances_for_owner(session, owner_id, [account.id])[account.id] != 0:
        raise Conflict("account_balance_not_zero")
    account.archived_at = clock.now()
    session.commit()
    return account


def unarchive_account(
    session: Session, owner_id: uuid.UUID, account_id: uuid.UUID
) -> Account:
    """Vuelve a aceptar movimientos. Un bolsillo exige su banco activo (CL-30)."""
    account = get_account(session, owner_id, account_id)
    if account.archived_at is None:
        raise Conflict("not_archived")
    if account.parent_id is not None:
        parent = get_account(session, owner_id, account.parent_id)
        if parent.archived_at is not None:
            raise Conflict("parent_archived", field="parent_id")
    account.archived_at = None
    session.commit()
    return account
