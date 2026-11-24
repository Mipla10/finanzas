"""T9: errores de dominio y catálogo de mensajes en español (RF-22, RNF-7)."""

import pytest

from finanzas.domain import messages
from finanzas.domain.errors import Conflict, DomainError, InvalidData, NotFound


@pytest.mark.parametrize(
    ("error_class", "error_type"),
    [(InvalidData, "invalid_data"), (NotFound, "not_found"), (Conflict, "conflict")],
)
def test_each_domain_error_has_its_type(
    error_class: type[DomainError], error_type: str
) -> None:
    error = error_class("resource_not_found", field="account_id")
    assert error.error_type == error_type
    assert error.field == "account_id"
    assert error.message == messages.MESSAGES["resource_not_found"]


def test_message_comes_from_catalog_with_its_parameters() -> None:
    error = InvalidData("invalid_value", field="amount_cents")
    assert error.message == messages.render("invalid_value")
    assert str(error) == error.message


def test_render_fills_parameters() -> None:
    assert "60" in messages.render("too_long", max_length=60)


def test_unknown_code_is_a_programming_error() -> None:
    with pytest.raises(KeyError):
        messages.render("codigo-que-no-existe")


def test_every_catalog_message_is_non_empty_spanish_text() -> None:
    assert messages.MESSAGES
    for code, text in messages.MESSAGES.items():
        assert text.strip(), code
        assert text.rstrip().endswith("."), code
