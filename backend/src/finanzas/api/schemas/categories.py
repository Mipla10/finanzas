"""Esquemas de categorías (RF-6, plan §4.2)."""

import uuid

from pydantic import BaseModel

from finanzas.api.schemas.common import BogotaDatetime, RequestModel
from finanzas.db.models import Category
from finanzas.domain.categories import CategoryKind


class CategoryCreate(RequestModel):
    name: str
    kind: CategoryKind


class CategoryRename(RequestModel):
    """Solo se renombra: la clase nunca cambia (RF-6)."""

    name: str


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: CategoryKind
    archived: bool
    created_at: BogotaDatetime

    @classmethod
    def of(cls, category: Category) -> "CategoryOut":
        return cls(
            id=category.id,
            name=category.name,
            kind=category.kind,
            archived=category.archived_at is not None,
            created_at=category.created_at,
        )


class CategoryList(BaseModel):
    items: list[CategoryOut]
