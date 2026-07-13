"""Shared pytest fixtures.

DB-backed tests require the docker compose stack up AND the corpus seeded
(`make up && python scripts/seed.py`). They are skipped automatically if the
database is unreachable, so the suite still runs in a bare environment.
"""
import pytest
from sqlalchemy import text

from app.db import SessionLocal, engine


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(), reason="database not reachable (run `make up` + seed)"
)


@pytest.fixture
def session():
    with SessionLocal() as s:
        yield s
