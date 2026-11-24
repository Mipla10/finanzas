"""T18: reglas de fecha (RF-2, CL-6, CL-8, CL-9, CL-10, plan §3.5)."""

from datetime import date, datetime, timedelta

import pytest

from finanzas.domain.dates import (
    BOGOTA,
    validate_movement_date,
    validate_start_date,
)
from finanzas.domain.errors import InvalidData

TODAY = date(2026, 11, 23)
START = date(2026, 11, 1)


def check(movement_date: date, **starts: date) -> date:
    return validate_movement_date(
        movement_date, today=TODAY, account_starts=starts or {"Banco Prueba": START}
    )


# --- Fecha de un movimiento ---


def test_today_and_past_dates_are_accepted() -> None:
    assert check(TODAY) == TODAY
    assert check(date(2026, 11, 10)) == date(2026, 11, 10)


def test_cl_6_tomorrow_is_rejected() -> None:
    with pytest.raises(InvalidData) as caught:
        check(TODAY + timedelta(days=1))
    assert (caught.value.code, caught.value.field) == ("date_in_future", "date")


def test_cl_8_date_equal_to_account_start_is_accepted() -> None:
    assert check(START) == START


def test_cl_9_date_before_account_start_is_rejected_naming_the_account() -> None:
    with pytest.raises(InvalidData) as caught:
        check(START - timedelta(days=1))
    assert (caught.value.code, caught.value.field) == (
        "date_before_account_start",
        "date",
    )
    assert "Banco Prueba" in caught.value.message
    assert "2026-11-01" in caught.value.message


def test_every_involved_account_is_checked() -> None:
    # Transferencia: Efectivo empezó después; la fecha es válida para Banco pero no
    # para Efectivo, así que se rechaza nombrando a Efectivo.
    with pytest.raises(InvalidData) as caught:
        check(
            date(2026, 11, 5),
            **{"Banco Prueba": START, "Efectivo Prueba": date(2026, 11, 10)},
        )
    assert "Efectivo Prueba" in caught.value.message


def test_future_check_comes_before_start_check() -> None:
    with pytest.raises(InvalidData) as caught:
        check(TODAY + timedelta(days=1), **{"Cuenta Nueva": TODAY + timedelta(days=5)})
    assert caught.value.code == "date_in_future"


def test_datetime_is_not_a_movement_date() -> None:
    with pytest.raises(InvalidData) as caught:
        check(datetime(2026, 11, 20, 10, 0, tzinfo=BOGOTA))
    assert (caught.value.code, caught.value.field) == ("date_invalid", "date")


# --- Fecha de inicio de una cuenta ---


def test_start_date_today_or_past_is_accepted() -> None:
    assert validate_start_date(TODAY, today=TODAY) == TODAY
    assert validate_start_date(START, today=TODAY) == START


def test_cl_10_future_start_date_is_rejected() -> None:
    with pytest.raises(InvalidData) as caught:
        validate_start_date(TODAY + timedelta(days=1), today=TODAY)
    assert (caught.value.code, caught.value.field) == (
        "start_date_in_future",
        "start_date",
    )


def test_start_date_with_time_is_rejected() -> None:
    with pytest.raises(InvalidData) as caught:
        validate_start_date(datetime(2026, 11, 1, 8, 0, tzinfo=BOGOTA), today=TODAY)
    assert (caught.value.code, caught.value.field) == ("date_invalid", "start_date")
