"""Shared pytest fixtures.

DB-backed tests require the docker compose stack up AND the corpus seeded
(`make up && python scripts/seed.py`). They are skipped automatically if the
database is unreachable, so the suite still runs in a bare environment.
"""
import pytest
from sqlalchemy import select, text

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


@pytest.fixture
def embedded_recipes(session):
    """Guarantee several Recipe rows carry a real embedding vector.

    CI's seed script loads the corpus but never runs the embedder (that would
    mean downloading the sentence-transformers model on every run), so
    `embedding IS NOT NULL` matches nothing there even though a full local
    dev DB has embeddings backfilled. Personalization tests need at least one
    embedded recipe regardless of which environment they run in, so this
    fixture writes distinct synthetic (orthogonal one-hot) vectors directly
    and restores the original values on teardown.
    """
    from app.models import Recipe

    rows = session.execute(select(Recipe).order_by(Recipe.id).limit(4)).scalars().all()
    assert len(rows) >= 2, "seed corpus must have at least 2 recipes"
    originals = [r.embedding for r in rows]
    for i, r in enumerate(rows):
        vec = [0.0] * 384
        vec[i] = 1.0
        r.embedding = vec
    session.commit()
    try:
        yield rows
    finally:
        for r, orig in zip(rows, originals):
            r.embedding = orig
        session.commit()
