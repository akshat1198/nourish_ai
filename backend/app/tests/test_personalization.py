"""Personalization tests.

Cold-start / disabled paths must degrade to {}/None identically to the
baseline (unpersonalized) behaviour. The safety guarantee (taste only
reorders an already-filtered set) is exercised at the ranking layer here
and verified end-to-end live in Chrome.
"""
from sqlalchemy import select

from app.models import Recipe, SavedRecipe
from app.schemas.recommend import RecipeCandidate
from app.services.personalization import taste_scores, taste_vector
from app.services.ranking import rank
from app.tests.conftest import requires_db


def _candidate(id_: int, **overrides) -> RecipeCandidate:
    base = dict(
        id=id_,
        title=f"Recipe {id_}",
        time_minutes=30,
        diet_labels=[],
        allergens=[],
        tags=[],
        cuisine=None,
        region=None,
        meal_types=[],
        nutrition={},
        matched_ingredients=["a"],
        missing_ingredients=[],
        matched_essential=1,
        total_essential=1,
    )
    base.update(overrides)
    return RecipeCandidate(**base)


@requires_db
def test_cold_start_taste_vector_is_none(session):
    uk = "personalization-cold-start"
    session.query(SavedRecipe).filter_by(user_key=uk).delete()
    session.commit()
    try:
        assert taste_vector(session, uk) is None
        assert taste_scores(session, uk, [1, 2, 3]) == {}
    finally:
        session.query(SavedRecipe).filter_by(user_key=uk).delete()
        session.commit()


@requires_db
def test_taste_vector_and_scores_after_saving_a_recipe(session):
    uk = "personalization-saved-paneer"
    paneer = session.execute(
        select(Recipe).where(
            Recipe.title.ilike("%paneer%"), Recipe.embedding.isnot(None)
        )
    ).scalars().first()
    assert paneer is not None, "expected at least one embedded paneer recipe"

    other = session.execute(
        select(Recipe.id).where(Recipe.id != paneer.id, Recipe.embedding.isnot(None)).limit(3)
    ).scalars().all()

    session.query(SavedRecipe).filter_by(user_key=uk).delete()
    session.commit()
    try:
        session.add(SavedRecipe(user_key=uk, recipe_id=paneer.id))
        session.commit()

        vec = taste_vector(session, uk)
        assert vec is not None
        assert len(vec) == 384  # embedder dim

        ids = [paneer.id] + other
        scores = taste_scores(session, uk, ids, vec)
        assert scores  # non-empty
        assert paneer.id in scores
        # the saved recipe should score at (or extremely near) the ceiling —
        # its own embedding is the (sole) input to the taste vector.
        assert scores[paneer.id] >= max(scores.values()) - 1e-6
    finally:
        session.query(SavedRecipe).filter_by(user_key=uk).delete()
        session.commit()


def test_rank_with_taste_scores_reorders_by_taste():
    a = _candidate(1)
    b = _candidate(2)
    # identical base scores; taste should decide the order.
    with_taste = rank([a, b], limit=2, taste_scores={1: 0.9})
    assert [r.id for r in with_taste] == [1, 2]
    assert "matches recipes you've saved" in with_taste[0].why


def test_rank_without_taste_scores_preserves_base_order():
    a = _candidate(1)
    b = _candidate(2, time_minutes=10)  # b has a better time_fit -> higher base score
    no_taste = rank([a, b], limit=2)
    with_none = rank([a, b], limit=2, taste_scores=None)
    assert [r.id for r in no_taste] == [r.id for r in with_none]
    assert "matches recipes you've saved" not in no_taste[0].why
    assert "matches recipes you've saved" not in no_taste[1].why


@requires_db
def test_recommend_endpoint_cold_start_unaffected(session):
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    resp = c.post(
        "/v1/recommendations",
        json={"pantry": ["garlic", "onion", "tomato"], "limit": 5},
        headers={"X-User-Key": "personalization-cold-start-endpoint"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] in {"normal", "relaxed", "substitution_first", "shopping_assisted"}


@requires_db
def test_personalized_responses_are_never_cached(session):
    """Regression: a personalized user re-issuing the IDENTICAL request right
    after a feedback write (e.g. dismissing a recipe) must get a freshly
    computed response, not a stale one from the response cache. The response
    cache's `user` key component only prevents CROSS-user collisions — it does
    nothing for this same-user, same-request staleness, which the taste-vector
    cache invalidation alone doesn't fix either (they're two different caches)."""
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    uk = "personalization-cache-bypass-regression"
    paneer = session.execute(
        select(Recipe).where(
            Recipe.title.ilike("%paneer%"), Recipe.embedding.isnot(None)
        )
    ).scalars().first()
    assert paneer is not None

    session.query(SavedRecipe).filter_by(user_key=uk).delete()
    session.commit()
    try:
        session.add(SavedRecipe(user_key=uk, recipe_id=paneer.id))
        session.commit()

        req = {"pantry": ["paneer", "onion", "garlic"], "limit": 10}
        r1 = c.post("/v1/recommendations", json=req, headers={"X-User-Key": uk})
        assert r1.headers["x-cache"] == "skip-personalized"

        r2 = c.post("/v1/recommendations", json=req, headers={"X-User-Key": uk})
        assert r2.headers["x-cache"] == "skip-personalized", (
            "a personalized user's identical request was served from cache — "
            "a feedback write between two such requests would silently be ignored"
        )
    finally:
        session.query(SavedRecipe).filter_by(user_key=uk).delete()
        session.commit()
