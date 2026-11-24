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
    session: Session,
    owner_id: uuid.UUID,
    kind: CategoryKind | None = None,
    include_archived: bool = False,
) -> list[Category]:
    return repo.list_owned(session, owner_id, kind, include_archived)


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


def archive_category(
    session: Session, owner_id: uuid.UUID, clock: Clock, category_id: uuid.UUID
) -> Category:
    """Deja de ofrecerse en movimientos nuevos; los existentes la conservan (RF-6)."""
    category = get_category(session, owner_id, category_id)
    if category.archived_at is not None:
        raise Conflict("already_archived")
    category.archived_at = clock.now()
    session.commit()
    return category


def unarchive_category(
    session: Session, owner_id: uuid.UUID, category_id: uuid.UUID
) -> Category:
    category = get_category(session, owner_id, category_id)
    if category.archived_at is None:
        raise Conflict("not_archived")
    category.archived_at = None
    session.commit()
    return category


def delete_category(
    session: Session, owner_id: uuid.UUID, category_id: uuid.UUID
) -> None:
    """Borra una categoría que NUNCA se usó (RF-6, plan §3.8). Si se usó, se archiva."""
    category = get_category(session, owner_id, category_id)
    if repo.used_by_movements(session, owner_id, category.id):
        raise Conflict("category_in_use")
    session.delete(category)
    session.commit()
