"""T1: el paquete existe, se importa y está instalado con su versión."""

from importlib.metadata import version


def test_package_imports_and_exposes_installed_version() -> None:
    import finanzas

    assert finanzas.__version__ == version("finanzas")
