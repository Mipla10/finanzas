"""Engine y base declarativa de los modelos (plan §1.2)."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase madre de todos los modelos; Alembic lee su metadata."""


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)
