"""Endpoints de categorías (RF-6, plan §4.2)."""

import uuid

from fastapi import APIRouter, Response, status

from finanzas.api.deps import ClockDep, OwnerDep, SessionDep
from finanzas.api.schemas.categories import (
    CategoryCreate,
    CategoryList,
    CategoryOut,
    CategoryRename,
)
from finanzas.api.schemas.errors import error_responses
from finanzas.domain.categories import CategoryKind
from finanzas.services import categories as service

router = APIRouter(prefix="/categories", tags=["categorías"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Crear categoría",
    response_description="Categoría creada.",
    responses=error_responses(409, 422),
)
def create_category(
    body: CategoryCreate, session: SessionDep, owner_id: OwnerDep, clock: ClockDep
) -> CategoryOut:
    """Crea una categoría de gasto o de ingreso (RF-6). El nombre es único dentro de
    cada clase.
    """
    category = service.create_category(
        session, owner_id, clock, name=body.name, kind=body.kind
    )
    return CategoryOut.of(category)


@router.get(
    "",
    summary="Listar categorías",
    response_description="Categorías del usuario.",
    responses=error_responses(422),
)
def list_categories(
    session: SessionDep,
    owner_id: OwnerDep,
    kind: CategoryKind | None = None,
    include_archived: bool = False,
) -> CategoryList:
    """Lista las categorías, filtrables por clase con `kind`. Las archivadas solo
    aparecen con `include_archived=true`.
    """
    categories = service.list_categories(session, owner_id, kind, include_archived)
    return CategoryList(items=[CategoryOut.of(c) for c in categories])


@router.patch(
    "/{category_id}",
    summary="Renombrar categoría",
    response_description="Categoría renombrada.",
    responses=error_responses(404, 409, 422),
)
def rename_category(
    category_id: uuid.UUID,
    body: CategoryRename,
    session: SessionDep,
    owner_id: OwnerDep,
) -> CategoryOut:
    """Renombra la categoría; el nombre nuevo se ve en todos sus movimientos (RF-6). La
    clase no se puede cambiar.
    """
    category = service.rename_category(session, owner_id, category_id, name=body.name)
    return CategoryOut.of(category)


@router.post(
    "/{category_id}/archive",
    summary="Archivar categoría",
    response_description="Categoría archivada.",
    responses=error_responses(404, 409, 422),
)
def archive_category(
    category_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep, clock: ClockDep
) -> CategoryOut:
    """Archiva la categoría: deja de aceptarse en movimientos nuevos y los existentes la
    conservan.
    """
    category = service.archive_category(session, owner_id, clock, category_id)
    return CategoryOut.of(category)


@router.post(
    "/{category_id}/unarchive",
    summary="Desarchivar categoría",
    response_description="Categoría activa de nuevo.",
    responses=error_responses(404, 409, 422),
)
def unarchive_category(
    category_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> CategoryOut:
    """Vuelve a aceptar la categoría en movimientos nuevos."""
    return CategoryOut.of(service.unarchive_category(session, owner_id, category_id))


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Borrar categoría nunca usada",
    response_description="Categoría borrada.",
    responses=error_responses(404, 409, 422),
)
def delete_category(
    category_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> Response:
    """Borra una categoría que nunca se usó (RF-6). Si ya se usó, se archiva."""
    service.delete_category(session, owner_id, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
