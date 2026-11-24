"""Consultas de categorías, siempre limitadas al dueño (RNF-5)."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from finanzas.db.models import Category
from finanzas.domain.categories import CategoryKind


def get_owned(
    session: Session, owner_id: uuid.UUID, category_id: uuid.UUID
) -> Category | None:
    """La categoría si existe Y es del dueño; si es de otro, como si no existiera."""
    return session.scalar(
        select(Category).where(
            Category.id == category_id, Category.owner_id == owner_id
        )
    )


def name_taken(
    session: Session,
    owner_id: uuid.UUID,
    kind: CategoryKind,
    name_key: str,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    """¿Otra categoría del dueño, de esa clase, usa ese nombre?"""
    query = select(Category.id).where(
        Category.owner_id == owner_id,
        Category.kind == kind,
        Category.name_key == name_key,
    )
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    return bool(session.scalar(select(exists(query))))


def list_owned(
    session: Session, owner_id: uuid.UUID, kind: CategoryKind | None
) -> list[Category]:
    """Categorías activas del dueño, opcionalmente de una sola clase."""
    query = select(Category).where(
        Category.owner_id == owner_id, Category.archived_at.is_(None)
    )
    if kind is not None:
        query = query.where(Category.kind == kind)
    return list(session.scalars(query.order_by(Category.name_key, Category.kind)))
