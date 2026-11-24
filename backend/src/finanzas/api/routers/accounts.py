"""Endpoints de cuentas (RF-4, RF-5, plan §4.2)."""

import uuid

from fastapi import APIRouter, Response, status

from finanzas.api.deps import ClockDep, OwnerDep, SessionDep
from finanzas.api.routers.movements import movement_out
from finanzas.api.schemas.accounts import (
    AccountCreate,
    AccountList,
    AccountOut,
    AccountUpdate,
)
from finanzas.api.schemas.adjustments import (
    AdjustedOut,
    AdjustmentRequest,
    AlreadyBalancedOut,
)
from finanzas.api.schemas.errors import error_responses
from finanzas.api.schemas.movements import WarningOut
from finanzas.services import accounts as service
from finanzas.services.adjustments import adjust_balance

router = APIRouter(prefix="/accounts", tags=["cuentas"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Crear cuenta",
    response_description="Cuenta creada.",
    responses=error_responses(404, 409, 422),
)
def create_account(
    body: AccountCreate, session: SessionDep, owner_id: OwnerDep, clock: ClockDep
) -> AccountOut:
    """Crea una cuenta con su saldo inicial (RF-4). El saldo inicial es el del comienzo
    de `start_date` (por defecto, hoy). Un bolsillo exige `parent_id`: un banco
    activo.
    """
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


@router.get(
    "",
    summary="Listar cuentas",
    response_description="Cuentas del usuario.",
    responses=error_responses(422),
)
def list_accounts(
    session: SessionDep, owner_id: OwnerDep, include_archived: bool = False
) -> AccountList:
    """Lista las cuentas del usuario. Las archivadas solo aparecen con
    `include_archived=true`.
    """
    accounts = service.list_accounts(session, owner_id, include_archived)
    return AccountList(items=[AccountOut.of(a) for a in accounts])


@router.get(
    "/{account_id}",
    summary="Ver cuenta",
    response_description="La cuenta.",
    responses=error_responses(404, 422),
)
def get_account(
    account_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> AccountOut:
    """Devuelve una cuenta del usuario."""
    return AccountOut.of(service.get_account(session, owner_id, account_id))


@router.patch(
    "/{account_id}",
    summary="Renombrar o editar saldo y fecha inicial",
    response_description="Cuenta actualizada.",
    responses=error_responses(404, 409, 422),
)
def update_account(
    account_id: uuid.UUID,
    body: AccountUpdate,
    session: SessionDep,
    owner_id: OwnerDep,
    clock: ClockDep,
) -> AccountOut:
    """Renombra la cuenta o edita su saldo y fecha inicial (RF-5). Lo que no se envía no
    cambia. El saldo y la fecha inicial solo se editan si la cuenta no tiene
    movimientos; si los tiene, se corrige con un ajuste. El tipo y la cuenta padre no
    se pueden cambiar.
    """
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


@router.post(
    "/{account_id}/archive",
    summary="Archivar cuenta",
    response_description="Cuenta archivada.",
    responses=error_responses(404, 409, 422),
)
def archive_account(
    account_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep, clock: ClockDep
) -> AccountOut:
    """Archiva la cuenta: deja de aceptar movimientos nuevos (RF-5). Exige saldo en cero
    y ningún bolsillo activo.
    """
    return AccountOut.of(service.archive_account(session, owner_id, clock, account_id))


@router.post(
    "/{account_id}/unarchive",
    summary="Desarchivar cuenta",
    response_description="Cuenta activa de nuevo.",
    responses=error_responses(404, 409, 422),
)
def unarchive_account(
    account_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> AccountOut:
    """Vuelve a aceptar movimientos en la cuenta. Un bolsillo exige que su banco esté
    activo.
    """
    return AccountOut.of(service.unarchive_account(session, owner_id, account_id))


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Borrar cuenta nunca usada",
    response_description="Cuenta borrada.",
    responses=error_responses(404, 409, 422),
)
def delete_account(
    account_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> Response:
    """Borra una cuenta que nunca se usó (RF-5). Si ya se usó, se archiva."""
    service.delete_account(session, owner_id, account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{account_id}/adjustments",
    status_code=status.HTTP_201_CREATED,
    summary="Ajustar al saldo real de hoy",
    responses={
        **error_responses(404, 409, 422),
        status.HTTP_200_OK: {
            "model": AlreadyBalancedOut,
            "description": "La cuenta ya cuadra: no se crea ningún movimiento.",
        },
    },
    response_description="Ajuste creado.",
)
def adjust_account(
    account_id: uuid.UUID,
    body: AdjustmentRequest,
    response: Response,
    session: SessionDep,
    owner_id: OwnerDep,
    clock: ClockDep,
) -> AdjustedOut | AlreadyBalancedOut:
    """Compara el saldo real que ves hoy en el banco con el saldo propio de la cuenta
    (sin sus bolsillos) y crea un ajuste de entrada o de salida por la diferencia,
    con fecha de hoy (RF-12). Si ya cuadra, responde 200 y no crea nada.
    """
    result = adjust_balance(
        session,
        owner_id,
        clock,
        account_id,
        real_balance_cents=body.real_balance_cents,
    )
    if result.movement is None:
        response.status_code = status.HTTP_200_OK
        return AlreadyBalancedOut(
            status="already_balanced",
            movement=None,
            balance_cents=result.balance_cents,
            warnings=[],
        )
    return AdjustedOut(
        status="adjusted",
        movement=movement_out(session, owner_id, result.movement),
        warnings=[WarningOut.of(w) for w in result.warnings],
    )
