"""T17: normalización de nombres, comercio y textos libres (RF-13, CL-24, CL-33)."""

import pytest

from finanzas.domain import text
from finanzas.domain.errors import InvalidData

# --- Forma mostrada y clave de comparación (plan §5.3) ---


@pytest.mark.parametrize(
    ("raw", "shown"),
    [
        ("  rappi ", "rappi"),
        ("Mc   Donalds", "Mc Donalds"),
        ("\tTienda\n Prueba ", "Tienda Prueba"),
        ("RAPPI", "RAPPI"),  # se muestra tal cual la escribiste
    ],
)
def test_display_form_trims_and_collapses_spaces(raw: str, shown: str) -> None:
    assert text.display_form(raw) == shown


@pytest.mark.parametrize("raw", [None, "", "   ", "\t\n"])
def test_empty_or_blank_text_is_absent(raw: str | None) -> None:
    assert text.display_form(raw) is None
    assert text.text_key(raw) is None


def test_cl_24_same_merchant_regardless_of_spaces_and_case() -> None:
    keys = {text.text_key(raw) for raw in ["  rappi ", "RAPPI", "Rappi", "rAppI"]}
    assert keys == {"rappi"}


def test_cl_33_account_names_collide_ignoring_case() -> None:
    assert text.text_key("nequi") == text.text_key("Nequi")


def test_accents_are_kept_so_exito_and_éxito_differ() -> None:
    assert text.text_key("Éxito") != text.text_key("Exito")


def test_key_uses_casefold_not_just_lower() -> None:
    # casefold es un «lower» más completo para Unicode: «ß» equivale a «ss».
    assert text.text_key("Straße") == text.text_key("STRASSE")


# --- Nombres obligatorios: cuentas (60) y categorías (40) ---


def test_normalize_name_returns_display_and_key() -> None:
    assert text.normalize_name("  Banco   Prueba ", field="name", max_length=60) == (
        "Banco Prueba",
        "banco prueba",
    )


@pytest.mark.parametrize("raw", ["", "    ", None])
def test_empty_name_is_required(raw: str | None) -> None:
    with pytest.raises(InvalidData) as caught:
        text.normalize_name(raw, field="name", max_length=60)
    assert (caught.value.code, caught.value.field) == ("required", "name")


@pytest.mark.parametrize(
    ("max_length", "limit_name"),
    [(60, "ACCOUNT_NAME_MAX"), (40, "CATEGORY_NAME_MAX")],
)
def test_name_length_limits(max_length: int, limit_name: str) -> None:
    assert getattr(text, limit_name) == max_length
    ok = "x" * max_length
    assert (
        text.normalize_name(f"  {ok}  ", field="name", max_length=max_length)[0] == ok
    )
    with pytest.raises(InvalidData) as caught:
        text.normalize_name(ok + "x", field="name", max_length=max_length)
    assert caught.value.code == "too_long"
    assert str(max_length) in caught.value.message


# --- Comercio (80): opcional, con clave ---


def test_normalize_merchant_returns_display_and_key() -> None:
    assert text.normalize_merchant("  Tienda   Prueba ") == (
        "Tienda Prueba",
        "tienda prueba",
    )
    assert text.normalize_merchant("   ") == (None, None)
    assert text.normalize_merchant(None) == (None, None)


def test_merchant_length_limit() -> None:
    assert text.MERCHANT_MAX == 80
    assert text.normalize_merchant("m" * 80)[0] == "m" * 80
    with pytest.raises(InvalidData) as caught:
        text.normalize_merchant("m" * 81)
    assert (caught.value.code, caught.value.field) == ("too_long", "merchant")


# --- Nota (500) y motivo de anulación (200): opcionales, conservan saltos ---


def test_note_keeps_inner_line_breaks_and_trims_ends() -> None:
    assert text.normalize_note("  línea 1\nlínea 2  ") == "línea 1\nlínea 2"
    assert text.normalize_note(" \n ") is None
    assert text.normalize_note(None) is None
    assert text.normalize_void_reason(None) is None


@pytest.mark.parametrize(
    ("function", "limit_name", "max_length", "field"),
    [
        ("normalize_note", "NOTE_MAX", 500, "note"),
        ("normalize_void_reason", "VOID_REASON_MAX", 200, "reason"),
    ],
)
def test_optional_text_limits(
    function: str, limit_name: str, max_length: int, field: str
) -> None:
    normalize = getattr(text, function)
    assert getattr(text, limit_name) == max_length
    assert normalize("n" * max_length) == "n" * max_length
    with pytest.raises(InvalidData) as caught:
        normalize("n" * (max_length + 1))
    assert (caught.value.code, caught.value.field) == ("too_long", field)
