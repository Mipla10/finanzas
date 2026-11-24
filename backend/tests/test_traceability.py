"""T56: cada caso límite de la spec tiene su test con nombre `test_cl_<n>_` (plan §9).

Así, buscar «test_cl_17_» lleva directo al test que comprueba CL-17.
"""

import re
from pathlib import Path

TESTS_DIR = Path(__file__).parent
EDGE_CASES = range(1, 40)  # CL-1 a CL-39 de la spec 001


def test_every_edge_case_has_a_named_test() -> None:
    names = set()
    for path in TESTS_DIR.rglob("test_*.py"):
        names.update(
            re.findall(r"^\s*def (test_cl_\d+_\w*)", path.read_text("utf-8"), re.M)
        )
    covered = {int(re.match(r"test_cl_(\d+)_", name)[1]) for name in names}  # type: ignore[index]
    missing = [f"CL-{n}" for n in EDGE_CASES if n not in covered]
    assert missing == []
