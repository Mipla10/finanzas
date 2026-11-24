"""T36: dos correcciones simultáneas del mismo movimiento (RF-19, DT-6, R-4).

Usa DOS conexiones reales (no la transacción que se deshace): por eso crea y
borra sus propios datos. Sin sleeps a ciegas: se consulta a PostgreSQL quién
está esperando un bloqueo.
"""

import threading
import time
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, delete, select, text
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, MovementVersion, User
from finanzas.db.repositories import movements as movements_repo
from finanzas.domain.accounts import AccountType
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.movements import MovementType
from finanzas.services import movements as service

INSTANT = "2026-11-23T10:00:00-05:00"


@pytest.fixture
def committed_expense(db_engine: Engine) -> Iterator[tuple[uuid.UUID, uuid.UUID]]:
    """Un gasto de 100 confirmado de verdad en la BD; se borra al terminar."""
    clock = FixedClock(INSTANT)
    owner_id = uuid.uuid4()
    with Session(db_engine) as session:
        session.add(User(id=owner_id, created_at=clock.now()))
        session.flush()  # el dueño primero: las cuentas lo referencian
        account = Account(
            id=uuid.uuid4(),
            owner_id=owner_id,
            name="Concurrencia Prueba",
            name_key="concurrencia prueba",
            type=AccountType.CASH,
            initial_balance_cents=0,
            start_date=clock.today(),
            created_at=clock.now(),
        )
        category = Category(
            id=uuid.uuid4(),
            owner_id=owner_id,
            name="Concurrencia Prueba",
            name_key="concurrencia prueba",
            kind=CategoryKind.EXPENSE,
            created_at=clock.now(),
        )
        session.add_all([account, category])
        session.commit()
        movement_id = service.create_movement(
            session,
            owner_id,
            clock,
            movement_type=MovementType.EXPENSE,
            amount_cents=100,
            from_account_id=account.id,
            category_id=category.id,
        ).movement.id
    try:
        yield owner_id, movement_id
    finally:
        with Session(db_engine) as session:
            for model in (MovementVersion, Movement, Category, Account):
                session.execute(delete(model).where(model.owner_id == owner_id))
            session.execute(delete(User).where(User.id == owner_id))
            session.commit()


def wait_until_someone_waits_for_a_lock(engine: Engine, timeout: float = 5) -> None:
    query = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() AND wait_event_type = 'Lock'"
    )
    deadline = time.monotonic() + timeout
    with engine.connect() as connection:
        while time.monotonic() < deadline:
            if connection.execute(query).scalar_one() > 0:
                return
            time.sleep(0.01)  # sondeo corto: no es una espera a ciegas
    raise AssertionError("La segunda corrección nunca quedó esperando el bloqueo")


def test_second_correction_waits_and_both_are_kept(
    db_engine: Engine, committed_expense: tuple[uuid.UUID, uuid.UUID]
) -> None:
    owner_id, movement_id = committed_expense
    outcome: dict[str, object] = {}

    def second_correction() -> None:
        try:
            with Session(db_engine) as session_b:
                result = service.correct_movement(
                    session_b,
                    owner_id,
                    FixedClock(INSTANT),
                    movement_id,
                    amount_cents=300,
                )
                outcome["version"] = result.movement.current_version
        except Exception as error:  # se reporta en el hilo principal
            outcome["error"] = error

    with Session(db_engine) as session_a:
        # A toma el bloqueo del movimiento y lo mantiene.
        movements_repo.get_owned_for_update(session_a, owner_id, movement_id)
        thread = threading.Thread(target=second_correction)
        thread.start()
        wait_until_someone_waits_for_a_lock(db_engine)  # B está esperando
        service.correct_movement(  # A corrige y, al confirmar, suelta el bloqueo
            session_a, owner_id, FixedClock(INSTANT), movement_id, amount_cents=200
        )
    thread.join(timeout=10)

    assert "error" not in outcome, outcome.get("error")
    assert outcome["version"] == 3
    with Session(db_engine) as session:
        history = session.execute(
            select(MovementVersion.version_no, MovementVersion.amount_cents)
            .where(MovementVersion.movement_id == movement_id)
            .order_by(MovementVersion.version_no)
        ).all()
        final = session.get(Movement, movement_id)
        assert final is not None
        assert [tuple(row) for row in history] == [(1, 100), (2, 200), (3, 300)]
        assert final.amount_cents == 300  # gana la última
