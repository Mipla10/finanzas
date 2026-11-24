"""Casos de uso de categorías (RF-6)."""

import uuid

from sqlalchemy.orm import Session

from finanzas.db.models import Category
from finanzas.db.repositories import categories as repo
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import Clock
from finanzas.domain.errors import Conflict, NotFound
from finanzas.domain.text import CATEGORY_NAME_MAX, normalize_name


def get_category(
    session: Session, owner_id: uuid.UUID, category_id: uuid.UUID
) -> Category:
    category = repo.get_owned(session, owner_id, category_id)
    if category is None:
        raise NotFound("resource_not_found", field="category_id")
    return category


def list_categories(
    session: Session, owner_id: uuid.UUID, kind: CategoryKind | None = None
) -> list[Category]:
    return repo.list_owned(session, owner_id, kind)


def _normalized_unique_name(
    session: Session,
    owner_id: uuid.UUID,
    kind: CategoryKind,
    name: str,
    exclude_id: uuid.UUID | None = None,
) -> tuple[str, str]:
    shown, name_key = normalize_name(name, field="name", max_length=CATEGORY_NAME_MAX)
    if repo.name_taken(session, owner_id, kind, name_key, exclude_id):
        raise Conflict("duplicate_category_name", field="name")
    return shown, name_key


def create_category(
    session: Session,
    owner_id: uuid.UUID,
    clock: Clock,
    *,
    name: str,
    kind: CategoryKind,
) -> Category:
    shown, name_key = _normalized_unique_name(session, owner_id, kind, name)
    category = Category(
        id=uuid.uuid4(),
        owner_id=owner_id,
        name=shown,
        name_key=name_key,
        kind=kind,
        created_at=clock.now(),
    )
    session.add(category)
    session.commit()
    return category


def rename_category(
    session: Session, owner_id: uuid.UUID, category_id: uuid.UUID, *, name: str
) -> Category:
    """Renombra (RF-6). La clase nunca cambia: alteraría los totales históricos."""
    category = get_category(session, owner_id, category_id)
    category.name, category.name_key = _normalized_unique_name(
        session, owner_id, category.kind, name, exclude_id=category.id
    )
    session.commit()
    return category
