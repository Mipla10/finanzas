"""T14: las migraciones van y vuelven, y coinciden con los modelos (regla 7)."""

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

TABLES = {"users", "accounts", "categories", "movements", "movement_versions"}


def test_migrations_go_down_to_base_and_back_up(
    db_engine: Engine, alembic_config: Config
) -> None:
    try:
        command.downgrade(alembic_config, "base")
        assert TABLES.isdisjoint(inspect(db_engine).get_table_names())
    finally:
        command.upgrade(alembic_config, "head")  # deja la BD lista para los demás
    assert set(inspect(db_engine).get_table_names()) >= TABLES


def test_models_and_migrations_say_the_same(
    db_engine: Engine, alembic_config: Config
) -> None:
    """Si alguien cambia un modelo sin crear su migración, esto falla."""
    command.check(alembic_config)
