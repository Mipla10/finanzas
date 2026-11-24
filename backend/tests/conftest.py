"""Utilería compartida por todos los tests (plan §8.2)."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finanzas.db.base import make_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]

# finanzas.main crea la app al importarse y exige contraseña (RNF-4).
# Valor fijo de prueba, no secreto; los tests de config lo quitan a propósito.
os.environ.setdefault("APP_PASSWORD", "contraseña-de-prueba-12")

# Valor por defecto = .env.example (credenciales solo locales, no secretas).
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://finanzas:finanzas@localhost:5432/finanzas_test",
)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Aplica las migraciones a la BD de pruebas una vez por corrida."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")
    engine = make_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Cada test corre dentro de una transacción que se deshace al final."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
