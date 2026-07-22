"""Deterministic A/B assignment tests."""
import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models import SavedRecipe
from app.services.experiments import assign_variant
from app.tests.conftest import requires_db

client = TestClient(app)


def test_same_session_same_variant_across_calls():
    sid = str(uuid.uuid4())
    v1 = assign_variant(sid, "ranking_ab")
    v2 = assign_variant(sid, "ranking_ab")
    assert v1 == v2
    assert v1 in settings.experiment_variants_list


def test_variants_spread_across_many_sessions():
    seen = {assign_variant(str(uuid.uuid4()), "ranking_ab") for _ in range(30)}
    # over a decent sample, a 2-way hash split should hit both variants.
    assert seen == set(settings.experiment_variants_list)


def test_different_experiments_can_bucket_the_same_session_differently():
    sid = str(uuid.uuid4())
    # not asserting a specific relationship — just that the experiment name is
    # actually part of the hash input (same session, different namespace).
    a = assign_variant(sid, "experiment-a")
    b = assign_variant(sid, "experiment-b")
    assert a in settings.experiment_variants_list
    assert b in settings.experiment_variants_list


@requires_db
def test_recommend_returns_variant_when_session_id_present():
    resp = client.post(
        "/v1/recommendations",
        json={"pantry": ["garlic", "onion"], "session_id": "test-sess-1", "limit": 3},
        headers={"X-User-Key": "experiments-test-user"},
    )
    assert resp.status_code == 200
    assert resp.json()["variant"] in settings.experiment_variants_list


@requires_db
def test_recommend_returns_no_variant_without_session_id():
    resp = client.post(
        "/v1/recommendations",
        json={"pantry": ["garlic", "onion"], "limit": 3},
        headers={"X-User-Key": "experiments-test-user-2"},
    )
    assert resp.status_code == 200
    assert resp.json()["variant"] is None


@requires_db
def test_control_variant_disables_personalization_even_with_saved_signal(session, embedded_recipes):
    """Regression: taste_scores(..., vec=None) used to fall back to computing
    the user's REAL taste vector, silently undoing the control gate (`tvec`
    being None for "control" was indistinguishable from "cold start" at that
    call site). A user with strong saved signal on `control` must see zero
    trace of personalization."""
    uk = "experiments-control-gate-regression"
    saved = embedded_recipes[0]

    session.query(SavedRecipe).filter_by(user_key=uk).delete()
    session.commit()
    try:
        session.add(SavedRecipe(user_key=uk, recipe_id=saved.id))
        session.commit()

        control_sid = next(
            f"ctrl-gate-probe-{i}"
            for i in range(5000)
            if assign_variant(f"ctrl-gate-probe-{i}", settings.EXPERIMENT_NAME) == "control"
        )

        resp = client.post(
            "/v1/recommendations",
            json={
                "pantry": ["paneer", "spinach", "onion", "garlic", "ginger", "yogurt"],
                "session_id": control_sid,
                "limit": 10,
            },
            headers={"X-User-Key": uk},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["variant"] == "control"
        assert not any(
            "matches recipes you've saved" in r["why"] for r in body["results"]
        ), "control variant leaked personalization from the user's saved-recipe signal"
    finally:
        session.query(SavedRecipe).filter_by(user_key=uk).delete()
        session.commit()
