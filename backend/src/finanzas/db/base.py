"""Engine y base declarativa de los modelos (plan §1.2)."""

from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase

# Nombres fijos y legibles para índices y restricciones: las migraciones son
# reproducibles y los errores de la BD dicen qué regla se rompió.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Clase madre de todos los modelos; Alembic lee su metadata."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)
