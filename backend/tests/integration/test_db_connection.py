"""T2: la base de datos de pruebas está levantada y responde."""

import os

from sqlalchemy import create_engine, text

# Valor por defecto = el de .env.example (credenciales solo locales, no secretas).
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://finanzas:finanzas@localhost:5432/finanzas_test"
)


def test_test_database_answers_select_1() -> None:
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
            assert conn.execute(text("SELECT current_database()")).scalar_one() == (
                "finanzas_test"
            )
    finally:
        engine.dispose()
