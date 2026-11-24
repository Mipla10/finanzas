"""T5: cada test deja la base de datos como la encontró (plan §8.2)."""

from sqlalchemy import text
from sqlalchemy.orm import Session

PROBE = "t5_rollback_probe"


def probe_exists(session: Session) -> bool:
    return session.execute(text(f"SELECT to_regclass('{PROBE}')")).scalar() is not None


def test_1_writes_inside_its_transaction(db_session: Session) -> None:
    assert not probe_exists(db_session)
    db_session.execute(text(f"CREATE TABLE {PROBE} (x integer)"))
    db_session.execute(text(f"INSERT INTO {PROBE} VALUES (1)"))
    db_session.commit()  # aun con commit, el rollback externo lo deshace
    assert db_session.execute(text(f"SELECT count(*) FROM {PROBE}")).scalar() == 1


def test_2_does_not_see_what_the_previous_test_wrote(db_session: Session) -> None:
    assert not probe_exists(db_session)
