"""T4: reloj inyectable con la hora de Bogotá (RF-2, RNF-8, plan §5.5)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from finanzas.domain.dates import BOGOTA, Clock, FixedClock, SystemClock


def test_system_clock_uses_bogota_time() -> None:
    clock = SystemClock()
    now = clock.now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(hours=-5)


def test_system_clock_today_is_bogota_date() -> None:
    before = datetime.now(BOGOTA).date()
    today = SystemClock().today()
    after = datetime.now(BOGOTA).date()
    assert today in {before, after}  # tolera pasar la medianoche durante el test


def test_fixed_clock_stays_where_it_was_set() -> None:
    clock = FixedClock("2026-11-23T10:00:00-05:00")
    assert clock.now() == datetime(2026, 11, 23, 15, 0, tzinfo=UTC)
    assert clock.today() == date(2026, 11, 23)
    assert clock.today() == date(2026, 11, 23)  # no avanza solo


def test_fixed_clock_crosses_midnight_in_bogota() -> None:
    clock = FixedClock("2026-11-23T23:59:59-05:00")
    assert clock.today() == date(2026, 11, 23)
    clock.advance(timedelta(seconds=1))
    assert clock.today() == date(2026, 11, 24)


def test_fixed_clock_today_uses_bogota_even_if_set_in_utc() -> None:
    # 04:30 UTC del 24 = 23:30 del 23 en Bogotá.
    clock = FixedClock(datetime(2026, 11, 24, 4, 30, tzinfo=UTC))
    assert clock.today() == date(2026, 11, 23)
    assert clock.now().utcoffset() == timedelta(hours=-5)


def test_fixed_clock_rejects_time_without_timezone() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        FixedClock(datetime(2026, 11, 23, 10, 0))


def test_both_clocks_fulfil_the_clock_interface() -> None:
    clocks: list[Clock] = [SystemClock(), FixedClock("2026-11-23T10:00:00-05:00")]
    for clock in clocks:
        assert isinstance(clock.now(), datetime)
        assert isinstance(clock.today(), date)
