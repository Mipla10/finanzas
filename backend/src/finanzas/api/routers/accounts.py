"""Endpoints de cuentas (RF-4, RF-5, plan §4.2)."""

import uuid

from fastapi import APIRouter, Response, status

from finanzas.api.deps import ClockDep, OwnerDep, SessionDep
from finanzas.api.schemas.accounts import (
    AccountCreate,
    AccountList,
    AccountOut,
    AccountUpdate,
)
from finanzas.services import accounts as service

router = APIRouter(prefix="/accounts", tags=["cuentas"])


@router.post("", status_code=status.HTTP_201_CREATED, summary="Crear cuenta")
def create_account(
    body: AccountCreate, session: SessionDep, owner_id: OwnerDep, clock: ClockDep
) -> AccountOut:
    account = service.create_account(
        session,
        owner_id,
        clock,
        name=body.name,
        account_type=body.type,
        initial_balance_cents=body.initial_balance_cents,
        start_date=body.start_date,
        parent_id=body.parent_id,
    )
    return AccountOut.of(account)


@router.get("", summary="Listar cuentas")
def list_accounts(
    session: SessionDep, owner_id: OwnerDep, include_archived: bool = False
) -> AccountList:
    accounts = service.list_accounts(session, owner_id, include_archived)
    return AccountList(items=[AccountOut.of(a) for a in accounts])


@router.get("/{account_id}", summary="Ver cuenta")
def get_account(
    account_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> AccountOut:
    return AccountOut.of(service.get_account(session, owner_id, account_id))


@router.patch("/{account_id}", summary="Renombrar o editar saldo y fecha inicial")
def update_account(
    account_id: uuid.UUID,
    body: AccountUpdate,
    session: SessionDep,
    owner_id: OwnerDep,
    clock: ClockDep,
) -> AccountOut:
    account = service.update_account(
        session,
        owner_id,
        clock,
        account_id,
        name=body.name,
        initial_balance_cents=body.initial_balance_cents,
        start_date=body.start_date,
    )
    return AccountOut.of(account)


@router.post("/{account_id}/archive", summary="Archivar cuenta")
def archive_account(
    account_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep, clock: ClockDep
) -> AccountOut:
    return AccountOut.of(service.archive_account(session, owner_id, clock, account_id))


@router.post("/{account_id}/unarchive", summary="Desarchivar cuenta")
def unarchive_account(
    account_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> AccountOut:
    return AccountOut.of(service.unarchive_account(session, owner_id, account_id))


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Borrar cuenta nunca usada",
)
def delete_account(
    account_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> Response:
    service.delete_account(session, owner_id, account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
