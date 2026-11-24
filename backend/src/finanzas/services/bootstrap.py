"""Usuario inicial y categorías precargadas (RF-3, plan §5.4).

Hasta la spec 004 existe un único usuario, creado al arrancar por primera vez.
"""

import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from finanzas.db.models import Category, User
from finanzas.domain.dates import Clock
from finanzas.domain.defaults import DEFAULT_CATEGORIES
from finanzas.domain.text import normalize_name

# Candado de la BD para que dos copias de la app no creen dos usuarios a la vez.
_BOOTSTRAP_LOCK_KEY = 1_001_001


def seed_default_categories(
    session: Session, owner_id: uuid.UUID, clock: Clock
) -> list[Category]:
    """Crea las categorías precargadas de un usuario. La 004 la reutilizará."""
    categories = []
    for raw_name, kind in DEFAULT_CATEGORIES:
        name, name_key = normalize_name(raw_name, field="name", max_length=40)
        categories.append(
            Category(
                id=uuid.uuid4(),
                owner_id=owner_id,
                name=name,
                name_key=name_key,
                kind=kind,
                created_at=clock.now(),
            )
        )
    session.add_all(categories)
    return categories


def ensure_initial_user(session: Session, clock: Clock) -> uuid.UUID:
    """Idempotente: crea el usuario y sus categorías solo si no hay ninguno."""
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": _BOOTSTRAP_LOCK_KEY}
    )
    existing = session.scalar(select(User.id).order_by(User.created_at).limit(1))
    if existing is not None:
        session.commit()  # libera el candado
        return existing
    user = User(id=uuid.uuid4(), created_at=clock.now())
    session.add(user)
    session.flush()
    seed_default_categories(session, user.id, clock)
    session.commit()
    return user.id
