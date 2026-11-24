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
from finanzas.domain.categories import CategoryKind
from finanzas.services import categories as service

router = APIRouter(prefix="/categories", tags=["categorías"])


@router.post("", status_code=status.HTTP_201_CREATED, summary="Crear categoría")
def create_category(
    body: CategoryCreate, session: SessionDep, owner_id: OwnerDep, clock: ClockDep
) -> CategoryOut:
    category = service.create_category(
        session, owner_id, clock, name=body.name, kind=body.kind
    )
    return CategoryOut.of(category)


@router.get("", summary="Listar categorías")
def list_categories(
    session: SessionDep,
    owner_id: OwnerDep,
    kind: CategoryKind | None = None,
    include_archived: bool = False,
) -> CategoryList:
    categories = service.list_categories(session, owner_id, kind, include_archived)
    return CategoryList(items=[CategoryOut.of(c) for c in categories])


@router.patch("/{category_id}", summary="Renombrar categoría")
def rename_category(
    category_id: uuid.UUID,
    body: CategoryRename,
    session: SessionDep,
    owner_id: OwnerDep,
) -> CategoryOut:
    category = service.rename_category(session, owner_id, category_id, name=body.name)
    return CategoryOut.of(category)


@router.post("/{category_id}/archive", summary="Archivar categoría")
def archive_category(
    category_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep, clock: ClockDep
) -> CategoryOut:
    category = service.archive_category(session, owner_id, clock, category_id)
    return CategoryOut.of(category)


@router.post("/{category_id}/unarchive", summary="Desarchivar categoría")
def unarchive_category(
    category_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> CategoryOut:
    return CategoryOut.of(service.unarchive_category(session, owner_id, category_id))


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Borrar categoría nunca usada",
)
def delete_category(
    category_id: uuid.UUID, session: SessionDep, owner_id: OwnerDep
) -> Response:
    service.delete_category(session, owner_id, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
