"""T54: RNF-3, p95 < 300 ms con 10.000 movimientos (plan §5.7, riesgo R-6).

Se mide en local con `uv run pytest -m perf -s`; la CI no lo corre porque su
máquina varía. Datos sintéticos con semilla fija, deshechos al final del test.
"""

import random
import statistics
import time
import uuid
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, MovementVersion, User
from finanzas.domain.accounts import AccountType
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.movements import MovementType

pytestmark = pytest.mark.perf

STORED = 10_000
SAMPLES = 100
P95_LIMIT_MS = 300
START = date(2026, 1, 1)
DAYS = (date(2026, 11, 23) - START).days


@pytest.fixture
def stored(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_account: Callable[..., Account],
    make_category: Callable[..., Category],
) -> dict[str, Any]:
    """10.000 movimientos de `owner_a` repartidos en el año, con su versión 1."""
    rng = random.Random(3)
    bank = make_account(owner_a, name="Banco Perf", start_date=START)
    accounts = [
        bank,
        make_account(owner_a, AccountType.POCKET, parent=bank, start_date=START),
        make_account(owner_a, AccountType.DIGITAL_WALLET, start_date=START),
        make_account(owner_a, AccountType.CASH, start_date=START),
    ]
    expense = [make_category(owner_a) for _ in range(10)]
    income = [make_category(owner_a, CategoryKind.INCOME) for _ in range(3)]

    now = clock.now()
    movements, versions = [], []
    for _ in range(STORED):
        kind = rng.choices(
            [MovementType.EXPENSE, MovementType.INCOME, MovementType.TRANSFER],
            weights=[8, 1, 1],
        )[0]
        source, target = rng.sample(accounts, 2)
        data = {
            "amount_cents": rng.randint(100, 50_000_000),
            "date": START + timedelta(days=rng.randint(0, DAYS)),
            "from_account_id": None if kind is MovementType.INCOME else source.id,
            "to_account_id": None if kind is MovementType.EXPENSE else target.id,
            "category_id": (
                rng.choice(expense).id
                if kind is MovementType.EXPENSE
                else rng.choice(income).id
                if kind is MovementType.INCOME
                else None
            ),
            "merchant": None,
            "merchant_key": None,
            "note": None,
        }
        movement_id = uuid.uuid4()
        movements.append(
            {
                "id": movement_id,
                "owner_id": owner_a.id,
                "type": kind,
                "adjustment_direction": None,
                "created_at": now,
                "updated_at": now,
                "current_version": 1,
                **data,
            }
        )
        versions.append(
            {
                "id": uuid.uuid4(),
                "owner_id": owner_a.id,
                "movement_id": movement_id,
                "version_no": 1,
                "changed_fields": [],
                "created_at": now,
                **data,
            }
        )
    db_session.execute(insert(Movement), movements)
    db_session.execute(insert(MovementVersion), versions)
    db_session.flush()
    return {"account": accounts[2].id, "category": expense[0].id}


def p95_ms(action: Callable[[], Any]) -> float:
    durations = []
    for _ in range(SAMPLES):
        start = time.perf_counter()
        action()
        durations.append((time.perf_counter() - start) * 1000)
    return statistics.quantiles(durations, n=100)[94]


def test_rnf_3_register_and_balances_p95_under_300_ms(
    client: TestClient, stored: dict[str, Any]
) -> None:
    body = {
        "type": "expense",
        "amount_cents": 2500,
        "from_account_id": str(stored["account"]),
        "category_id": str(stored["category"]),
        "merchant": "Tienda Perf",
    }

    def register() -> None:
        assert client.post("/api/v1/movements", json=body).status_code == 201

    def balances() -> None:
        assert client.get("/api/v1/balances").status_code == 200

    register_p95, balances_p95 = p95_ms(register), p95_ms(balances)
    print(
        f"\nRNF-3 con {STORED} movimientos: p95 registrar = {register_p95:.1f} ms, "
        f"p95 saldos = {balances_p95:.1f} ms"
    )
    assert register_p95 < P95_LIMIT_MS
    assert balances_p95 < P95_LIMIT_MS
