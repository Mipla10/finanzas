"""T41: lista de comercios usados (RF-13, plan §5.3)."""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from finanzas.db.models import Movement, User
from finanzas.domain.dates import FixedClock
from finanzas.domain.errors import InvalidData
from finanzas.services import merchants as service


def pairs(session: Session, owner: User, **kwargs: Any) -> list[tuple[str, int]]:
    return [
        (m.merchant, m.uses)
        for m in service.list_merchants(session, owner.id, **kwargs)
    ]


def test_grouped_ignoring_case_and_ordered_by_uses(
    db_session: Session, owner_a: User, make_movement: Callable[..., Movement]
) -> None:
    for merchant in ["rappi", "RAPPI", "  Rappi ", "D1", "d1", "Tienda Prueba"]:
        make_movement(owner_a, merchant=merchant)
    assert [uses for _, uses in pairs(db_session, owner_a)] == [3, 2, 1]


def test_shows_the_most_recent_form_and_breaks_ties_by_recency(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_movement: Callable[..., Movement],
) -> None:
    make_movement(owner_a, merchant="tienda vieja", on=date(2026, 11, 2))
    make_movement(owner_a, merchant="rappi", on=date(2026, 11, 3))
    clock.advance(timedelta(minutes=1))
    make_movement(owner_a, merchant="Rappi", on=date(2026, 11, 3))  # más reciente
    make_movement(owner_a, merchant="D1", on=date(2026, 11, 20))
    make_movement(owner_a, merchant="d1", on=date(2026, 11, 10))

    assert pairs(db_session, owner_a) == [
        ("D1", 2),  # empata con Rappi en usos, pero se usó más recientemente
        ("Rappi", 2),
        ("tienda vieja", 1),
    ]


def test_voided_movements_do_not_count(
    db_session: Session,
    clock: FixedClock,
    owner_a: User,
    make_movement: Callable[..., Movement],
) -> None:
    make_movement(owner_a, merchant="Rappi")
    voided = make_movement(owner_a, merchant="Rappi")
    only_voided = make_movement(owner_a, merchant="Anulado Prueba")
    voided.voided_at = only_voided.voided_at = clock.now()
    db_session.flush()
    assert pairs(db_session, owner_a) == [("Rappi", 1)]


def test_movements_without_merchant_are_ignored(
    db_session: Session, owner_a: User, make_movement: Callable[..., Movement]
) -> None:
    make_movement(owner_a)
    assert pairs(db_session, owner_a) == []


def test_never_shows_merchants_of_another_user(
    db_session: Session,
    owner_a: User,
    owner_b: User,
    make_movement: Callable[..., Movement],
) -> None:
    make_movement(owner_a, merchant="Mío Prueba")
    make_movement(owner_b, merchant="Ajeno Prueba")
    assert pairs(db_session, owner_a) == [("Mío Prueba", 1)]


def test_limit_is_respected_and_defaults_to_20(
    db_session: Session, owner_a: User, make_movement: Callable[..., Movement]
) -> None:
    for i in range(25):
        make_movement(owner_a, merchant=f"Comercio Prueba {i}")
    assert len(service.list_merchants(db_session, owner_a.id)) == 20
    assert len(service.list_merchants(db_session, owner_a.id, limit=3)) == 3


@pytest.mark.parametrize(("limit", "code"), [(0, "ge"), (201, "le")])
def test_limit_out_of_range_is_rejected(
    db_session: Session, owner_a: User, limit: int, code: str
) -> None:
    with pytest.raises(InvalidData) as caught:
        service.list_merchants(db_session, owner_a.id, limit=limit)
    assert (caught.value.code, caught.value.field) == (code, "limit")
