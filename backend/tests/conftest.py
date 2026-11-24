"""Utilería compartida por todos los tests (plan §8.2)."""

import itertools
import os
import uuid
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finanzas.api import deps
from finanzas.config import Settings
from finanzas.db.base import make_engine
from finanzas.db.models import Account, Category, Movement, MovementVersion, User
from finanzas.domain.accounts import AccountType
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.movements import AdjustmentDirection, MovementType

BACKEND_DIR = Path(__file__).resolve().parents[1]

# finanzas.main crea la app al importarse y exige contraseña (RNF-4).
# Valor fijo de prueba, no secreto; los tests de config lo quitan a propósito.
os.environ.setdefault("APP_PASSWORD", "clave-de-prueba-12")

# Valor por defecto = .env.example (credenciales solo locales, no secretas).
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://finanzas:finanzas@localhost:5432/finanzas_test",
)
# La app (Settings) también exige DATABASE_URL: en los tests, la BD de pruebas.
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    """Configuración de Alembic apuntando a la BD de pruebas."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return config


@pytest.fixture(scope="session")
def db_engine(alembic_config: Config) -> Iterator[Engine]:
    """Aplica las migraciones a la BD de pruebas una vez por corrida."""
    command.upgrade(alembic_config, "head")
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


# --- Datos sintéticos (plan §8.2). Nada real: nombres claramente inventados. ---

REFERENCE_INSTANT = "2026-11-23T10:00:00-05:00"
DEFAULT_START_DATE = date(2026, 11, 1)


@pytest.fixture
def clock() -> FixedClock:
    """Reloj detenido en el día de referencia de los ejemplos del plan."""
    return FixedClock(REFERENCE_INSTANT)


def _make_user(session: Session, clock: FixedClock) -> User:
    user = User(id=uuid.uuid4(), created_at=clock.now())
    session.add(user)
    session.flush()
    return user


@pytest.fixture
def owner_a(db_session: Session, clock: FixedClock) -> User:
    return _make_user(db_session, clock)


@pytest.fixture
def owner_b(db_session: Session, clock: FixedClock) -> User:
    """Segundo usuario: para probar que nadie ve datos ajenos (RNF-5)."""
    return _make_user(db_session, clock)


# --- Cliente HTTP (plan §8.2) ---

TEST_PASSWORD = "clave-de-prueba-12"
AUTH = {"Authorization": f"Bearer {TEST_PASSWORD}"}


@pytest.fixture
def client(db_session: Session, clock: FixedClock, owner_a: User) -> TestClient:
    """Cliente con contraseña, reloj fijo y la sesión con rollback del test.

    Actúa como `owner_a`. Sin `with`: no corre el arranque (lifespan), así que
    no siembra usuarios reales en la BD de pruebas.
    """
    # Aquí y no arriba: finanzas.main exige APP_PASSWORD al importarse.
    from finanzas.main import create_app

    settings = Settings(_env_file=None, app_password=TEST_PASSWORD, app_env="local")
    app = create_app(settings)
    app.dependency_overrides[deps.get_session] = lambda: db_session
    app.dependency_overrides[deps.get_clock] = lambda: clock
    app.dependency_overrides[deps.get_owner_id] = lambda: owner_a.id
    return TestClient(app, headers=AUTH, raise_server_exceptions=False)


@pytest.fixture
def make_account(db_session: Session, clock: FixedClock) -> Callable[..., Account]:
    counter = itertools.count(1)

    def factory(
        owner: User,
        account_type: AccountType = AccountType.BANK,
        *,
        name: str | None = None,
        parent: Account | None = None,
        initial_balance_cents: int = 0,
        start_date: date = DEFAULT_START_DATE,
    ) -> Account:
        name = name or f"Cuenta Prueba {next(counter)}"
        account = Account(
            id=uuid.uuid4(),
            owner_id=owner.id,
            name=name,
            name_key=name.strip().casefold(),
            type=account_type,
            parent_id=parent.id if parent else None,
            initial_balance_cents=initial_balance_cents,
            start_date=start_date,
            created_at=clock.now(),
        )
        db_session.add(account)
        db_session.flush()
        return account

    return factory


@pytest.fixture
def make_category(db_session: Session, clock: FixedClock) -> Callable[..., Category]:
    counter = itertools.count(1)

    def factory(
        owner: User,
        kind: CategoryKind = CategoryKind.EXPENSE,
        *,
        name: str | None = None,
    ) -> Category:
        name = name or f"Categoría Prueba {next(counter)}"
        category = Category(
            id=uuid.uuid4(),
            owner_id=owner.id,
            name=name,
            name_key=name.strip().casefold(),
            kind=kind,
            created_at=clock.now(),
        )
        db_session.add(category)
        db_session.flush()
        return category

    return factory


@pytest.fixture
def make_movement(
    db_session: Session,
    clock: FixedClock,
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> Callable[..., Movement]:
    """Crea un movimiento con su versión 1, como lo hará la app.

    Lo que no se indique se crea solo (cuentas, categoría) según el tipo.
    """

    def factory(
        owner: User,
        movement_type: MovementType = MovementType.EXPENSE,
        *,
        amount_cents: int = 2500000,
        on: date | None = None,
        from_account: Account | None = None,
        to_account: Account | None = None,
        category: Category | None = None,
        adjustment_direction: AdjustmentDirection | None = None,
        merchant: str | None = None,
        note: str | None = None,
    ) -> Movement:
        if movement_type is MovementType.ADJUSTMENT:
            adjustment_direction = adjustment_direction or AdjustmentDirection.IN
        needs_from = movement_type in {MovementType.EXPENSE, MovementType.TRANSFER} or (
            adjustment_direction is AdjustmentDirection.OUT
        )
        needs_to = movement_type in {
            MovementType.INCOME,
            MovementType.TRANSFER,
            MovementType.YIELD,
        } or (adjustment_direction is AdjustmentDirection.IN)
        if needs_from:
            from_account = from_account or make_account(owner)
        if needs_to:
            to_account = to_account or make_account(owner)
        if movement_type is MovementType.EXPENSE:
            category = category or make_category(owner, CategoryKind.EXPENSE)
        if movement_type is MovementType.INCOME:
            category = category or make_category(owner, CategoryKind.INCOME)

        now = clock.now()
        data = {
            "amount_cents": amount_cents,
            "date": on or clock.today(),
            "from_account_id": from_account.id if from_account else None,
            "to_account_id": to_account.id if to_account else None,
            "category_id": category.id if category else None,
            "merchant": merchant,
            "merchant_key": merchant.strip().casefold() if merchant else None,
            "note": note,
        }
        movement = Movement(
            id=uuid.uuid4(),
            owner_id=owner.id,
            type=movement_type,
            adjustment_direction=adjustment_direction,
            created_at=now,
            updated_at=now,
            current_version=1,
            **data,
        )
        db_session.add(movement)
        db_session.flush()
        db_session.add(
            MovementVersion(
                id=uuid.uuid4(),
                owner_id=owner.id,
                movement_id=movement.id,
                version_no=1,
                changed_fields=[],
                created_at=now,
                **data,
            )
        )
        db_session.flush()
        return movement

    return factory


@pytest.fixture
def month_scenario(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
    make_movement: Callable[..., Movement],
) -> dict[str, Account]:
    """Cuentas y movimientos M1–M8 de plan §2.4, de `owner_a`, por nombre.

    M2 queda con su monto corregido y M6 anulado (directo en la BD).
    """
    session, owner, T = db_session, owner_a, MovementType
    accounts = {}
    for name, kind, parent, initial in [
        ("Lulo", AccountType.BANK, None, 150000000),
        ("Ahorro", AccountType.POCKET, "Lulo", 300000000),
        ("Nequi", AccountType.DIGITAL_WALLET, None, 20000000),
        ("Efectivo", AccountType.CASH, None, 5000000),
    ]:
        accounts[name] = make_account(
            owner,
            kind,
            name=name,
            parent=accounts.get(parent or ""),
            initial_balance_cents=initial,
        )
        clock.advance(timedelta(seconds=1))  # orden de creación estable
    lulo, ahorro, nequi, cash = (
        accounts[n] for n in ("Lulo", "Ahorro", "Nequi", "Efectivo")
    )

    def day(d: int) -> date:
        return date(2026, 11, d)

    make_movement(owner, T.INCOME, to_account=lulo, amount_cents=200000000, on=day(1))
    m2 = make_movement(owner, from_account=nequi, amount_cents=2300000, on=day(3))
    m2.amount_cents = 2500000  # M2 corregido (versión 2)
    make_movement(
        owner,
        T.TRANSFER,
        from_account=lulo,
        to_account=cash,
        amount_cents=20000000,
        on=day(5),
    )
    make_movement(owner, from_account=lulo, amount_cents=700000, on=day(5))
    make_movement(
        owner,
        T.TRANSFER,
        from_account=lulo,
        to_account=ahorro,
        amount_cents=50000000,
        on=day(6),
    )
    m6 = make_movement(owner, from_account=cash, amount_cents=8000000, on=day(10))
    m6.voided_at = clock.now()  # M6 anulado
    make_movement(owner, T.YIELD, to_account=ahorro, amount_cents=1234567, on=day(20))
    make_movement(
        owner,
        T.ADJUSTMENT,
        from_account=nequi,
        amount_cents=350000,
        adjustment_direction=AdjustmentDirection.OUT,
        on=day(23),
    )
    session.flush()
    return accounts
