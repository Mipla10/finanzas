"""T24: el saldo calculado por la BD coincide con la fórmula pura (RF-15, DT-1).

Prueba de propiedades: 200 escenarios aleatorios con semilla fija (reproducible).
"""

import random
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from finanzas.db.models import Account, Category, Movement, User
from finanzas.db.repositories.balances import balances_for_owner
from finanzas.domain.accounts import AccountType
from finanzas.domain.balances import AccountInfo, Flow, compute_balances
from finanzas.domain.categories import CategoryKind
from finanzas.domain.dates import FixedClock
from finanzas.domain.movements import AdjustmentDirection, MovementType

SCENARIOS = 200
SEED = 42


def random_scenario(
    session: Session, clock: FixedClock, rng: random.Random, owner: User
) -> tuple[list[AccountInfo], list[Flow]]:
    """Crea en la BD cuentas y movimientos al azar; devuelve lo mismo «puro»."""
    accounts = [
        Account(
            id=uuid.uuid4(),
            owner_id=owner.id,
            name=f"Cuenta Prueba {i}",
            name_key=f"cuenta prueba {i}",
            type=rng.choice([AccountType.BANK, AccountType.CASH]),
            initial_balance_cents=rng.randint(-10_000_000, 10_000_000),
            start_date=clock.today(),
            created_at=clock.now(),
        )
        for i in range(rng.randint(1, 4))
    ]
    expense_cat, income_cat = (
        Category(
            id=uuid.uuid4(),
            owner_id=owner.id,
            name=f"Categoría Prueba {kind}",
            name_key=f"categoría prueba {kind}",
            kind=kind,
            created_at=clock.now(),
        )
        for kind in (CategoryKind.EXPENSE, CategoryKind.INCOME)
    )
    session.add_all([*accounts, expense_cat, income_cat])
    session.flush()

    movements, flows = [], []
    for _ in range(rng.randint(0, 15)):
        a, b = rng.choice(accounts), rng.choice(accounts)
        kind = rng.choice(
            ["expense", "income", "transfer", "yield", "adjust_in", "adjust_out"]
        )
        if kind == "transfer" and a.id == b.id:
            kind = "yield"  # una transferencia necesita dos cuentas distintas
        fields: dict = {
            "expense": {
                "type": MovementType.EXPENSE,
                "from_account_id": a.id,
                "category_id": expense_cat.id,
            },
            "income": {
                "type": MovementType.INCOME,
                "to_account_id": a.id,
                "category_id": income_cat.id,
            },
            "transfer": {
                "type": MovementType.TRANSFER,
                "from_account_id": a.id,
                "to_account_id": b.id,
            },
            "yield": {"type": MovementType.YIELD, "to_account_id": a.id},
            "adjust_in": {
                "type": MovementType.ADJUSTMENT,
                "to_account_id": a.id,
                "adjustment_direction": AdjustmentDirection.IN,
            },
            "adjust_out": {
                "type": MovementType.ADJUSTMENT,
                "from_account_id": a.id,
                "adjustment_direction": AdjustmentDirection.OUT,
            },
        }[kind]
        amount = rng.randint(1, 10_000_000)
        voided = rng.random() < 0.2
        movements.append(
            Movement(
                id=uuid.uuid4(),
                owner_id=owner.id,
                amount_cents=amount,
                date=clock.today(),
                created_at=clock.now(),
                updated_at=clock.now(),
                current_version=1,
                voided_at=clock.now() if voided else None,
                **fields,
            )
        )
        flows.append(
            Flow(
                fields.get("from_account_id"),
                fields.get("to_account_id"),
                amount,
                voided,
            )
        )
    session.add_all(movements)
    session.flush()

    infos = [
        AccountInfo(a.id, a.name, a.type, None, a.initial_balance_cents)
        for a in accounts
    ]
    return infos, flows


def test_sql_balances_match_pure_formula_in_200_random_scenarios(
    db_session: Session,
    clock: FixedClock,
    make_movement: Callable[..., Movement],
    owner_b: User,
) -> None:
    rng = random.Random(SEED)
    # Ruido: otro usuario con movimientos que NUNCA deben aparecer.
    for _ in range(5):
        make_movement(owner_b, MovementType.INCOME, amount_cents=99_999_999)

    for scenario in range(SCENARIOS):
        owner = User(id=uuid.uuid4(), created_at=clock.now())
        db_session.add(owner)
        db_session.flush()
        infos, flows = random_scenario(db_session, clock, rng, owner)

        sql = balances_for_owner(db_session, owner.id)

        assert sql == compute_balances(infos, flows), f"escenario {scenario}"
        assert all(type(value) is int for value in sql.values())  # entero exacto


def test_can_ask_only_for_some_accounts(
    db_session: Session,
    owner_a: User,
    make_account: Callable[..., Account],
    make_movement: Callable[..., Movement],
) -> None:
    lulo = make_account(owner_a, initial_balance_cents=1000)
    nequi = make_account(owner_a, initial_balance_cents=500)
    make_movement(owner_a, MovementType.YIELD, to_account=lulo, amount_cents=10)
    assert balances_for_owner(db_session, owner_a.id, [lulo.id]) == {lulo.id: 1010}
    assert balances_for_owner(db_session, owner_a.id) == {lulo.id: 1010, nequi.id: 500}


def test_accounts_of_another_owner_are_never_returned(
    db_session: Session,
    owner_a: User,
    owner_b: User,
    make_account: Callable[..., Account],
) -> None:
    theirs = make_account(owner_b, initial_balance_cents=777)
    assert balances_for_owner(db_session, owner_a.id, [theirs.id]) == {}
