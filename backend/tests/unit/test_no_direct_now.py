"""T4: guardián. Nadie consulta la hora por fuera del Clock (plan §5.5)."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "finanzas"

# Llamadas prohibidas: (objeto, método)
FORBIDDEN = {("date", "today"), ("datetime", "now"), ("func", "now")}

# Único lugar permitido: la clase SystemClock de domain/dates.py
ALLOWED = {("domain/dates.py", "SystemClock")}


def find_direct_clock_calls(source: str) -> list[tuple[int, str | None]]:
    """Devuelve (línea, clase que la contiene) de cada llamada prohibida."""
    found: list[tuple[int, str | None]] = []

    def visit(node: ast.AST, current_class: str | None) -> None:
        if isinstance(node, ast.ClassDef):
            current_class = node.name
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and (node.func.value.id, node.func.attr) in FORBIDDEN
        ):
            found.append((node.lineno, current_class))
        for child in ast.iter_child_nodes(node):
            visit(child, current_class)

    visit(ast.parse(source), None)
    return found


def test_guard_detects_forbidden_calls() -> None:
    sample = (
        "def f():\n"
        "    return date.today()\n"
        "class SystemClock:\n"
        "    def now(self):\n"
        "        return datetime.now(BOGOTA)\n"
        "x = func.now()\n"
    )
    assert find_direct_clock_calls(sample) == [(2, None), (5, "SystemClock"), (6, None)]


def test_guard_ignores_allowed_usage() -> None:
    assert find_direct_clock_calls("clock.now()\nclock.today()\n") == []


def test_source_code_only_asks_time_through_clock() -> None:
    violations = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC).as_posix()
        for line, cls in find_direct_clock_calls(path.read_text(encoding="utf-8")):
            if (relative, cls) not in ALLOWED:
                violations.append(f"{relative}:{line}")
    assert violations == [], f"Usa Clock en vez de la hora directa: {violations}"
