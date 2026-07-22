"""Profile/memory tests (AGENT-01/02, LLM-06)."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent.prompts import PROMPTS, system_prompt
from app.agent.validator import validate_plan
from app.main import app
from app.models import InteractionHistory, Recipe
from app.schemas.agent import AgentRequest, MealPlanItem, MealPlanResponse
from app.services.profile import (
    record_recommendations,
    recent_recommended,
    upsert_profile,
)
from app.schemas.profile import ProfileIn
from app.tests.conftest import requires_db

client = TestClient(app)


def test_prompt_versions_selectable():
    assert system_prompt("v1") == PROMPTS["v1"]
    assert system_prompt("v2") == PROMPTS["v2"]
    assert system_prompt("nope") == PROMPTS["v1"]  # unknown -> v1


@requires_db
def test_profile_put_then_get_roundtrip():
    body = {
        "diet": "vegetarian",
        "allergens": ["nuts"],
        "disliked_ingredients": ["mushroom"],
        "cuisine_prefs": ["italian"],
    }
    put = client.put("/v1/profile/tester1", json=body)
    assert put.status_code == 200
    got = client.get("/v1/profile/tester1").json()
    assert got["diet"] == "vegetarian"
    assert got["disliked_ingredients"] == ["mushroom"]


def test_profile_get_unknown_returns_empty_default():
    got = client.get("/v1/profile/nobody-here-xyz").json()
    assert got["user_key"] == "nobody-here-xyz"
    assert got["diet"] is None
    assert got["disliked_ingredients"] == []


@requires_db
def test_disliked_ingredient_is_a_validation_violation(session):
    # A mushroom recipe must fail validation when mushroom is disliked.
    mushroom_recipe = session.execute(
        select(Recipe).where(Recipe.title.like("%Mushroom%")).limit(1)
    ).scalar_one()
    plan = MealPlanResponse(
        recipes=[MealPlanItem(recipe_id=mushroom_recipe.id, title=mushroom_recipe.title, why="")],
        summary="",
    )
    v = validate_plan(session, plan, AgentRequest(disliked_ingredients=["mushroom"]))
    assert any(x["type"] == "disliked" for x in v)


@requires_db
def test_recent_recommended_roundtrip(session):
    tgp = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    # clean slate for this user
    session.query(InteractionHistory).filter_by(user_key="tester2").delete()
    session.commit()
    record_recommendations(session, "tester2", [tgp.id, tgp.id])  # dedup expected
    recent = recent_recommended(session, "tester2")
    assert [r["id"] for r in recent] == [tgp.id]
    assert recent[0]["title"] == "Tomato Garlic Pasta"


@requires_db
def test_feedback_endpoint_records(session):
    tgp = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    resp = client.post(
        "/v1/feedback", json={"user_key": "tester3", "recipe_id": tgp.id, "action": "cooked"}
    )
    assert resp.status_code == 200
    row = session.execute(
        select(InteractionHistory).where(
            InteractionHistory.user_key == "tester3",
            InteractionHistory.action == "cooked",
        )
    ).scalars().first()
    assert row is not None and row.recipe_id == tgp.id


def test_feedback_unknown_recipe_404():
    resp = client.post(
        "/v1/feedback", json={"user_key": "x", "recipe_id": 999999, "action": "cooked"}
    )
    assert resp.status_code == 404


def test_feedback_unknown_action_422():
    resp = client.post(
        "/v1/feedback", json={"user_key": "x", "recipe_id": 1, "action": "banana"}
    )
    assert resp.status_code == 422


@requires_db
def test_feedback_state_derives_made_and_rating(session):
    tgp = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    uk = "tester-fb-state"
    session.query(InteractionHistory).filter_by(user_key=uk).delete()
    session.commit()

    def post(action):
        assert (
            client.post(
                "/v1/feedback",
                json={"user_key": uk, "recipe_id": tgp.id, "action": action},
            ).status_code
            == 200
        )

    def state():
        return client.get(f"/v1/feedback/{uk}").json()["recipes"]

    # latest-wins per dimension; append-only log underneath.
    post("cooked")
    assert state()[str(tgp.id)] == {"made": True, "rating": None}
    post("liked")
    assert state()[str(tgp.id)] == {"made": True, "rating": "liked"}
    post("disliked")  # rating flips
    assert state()[str(tgp.id)]["rating"] == "disliked"
    post("uncooked")  # made toggles off
    assert state()[str(tgp.id)]["made"] is False
    post("unrated")  # rating cleared → recipe drops out (all-default)
    assert str(tgp.id) not in state()

    # the log kept every event (append-only), not just the final state
    n = session.query(InteractionHistory).filter_by(user_key=uk).count()
    assert n == 5


@requires_db
def test_feedback_write_invalidates_taste_cache(session):
    """A dismiss/like/etc. must bust the cached taste vector (Stage 12) so
    the next recommend reflects it immediately rather than waiting out
    TASTE_CACHE_TTL — otherwise a dismiss could feel like it did nothing."""
    from app.cache import redis_client
    from app.services.personalization import _taste_cache_key

    tgp = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    uk = "tester-taste-cache-invalidate"
    key = _taste_cache_key(uk)
    session.query(InteractionHistory).filter_by(user_key=uk).delete()
    session.commit()
    try:
        redis_client.set(key, '{"fake": "stale-cached-vector"}', ex=600)
        assert redis_client.get(key) is not None  # sanity: cache was populated

        resp = client.post(
            "/v1/feedback",
            json={"user_key": uk, "recipe_id": tgp.id, "action": "disliked"},
        )
        assert resp.status_code == 200
        assert redis_client.get(key) is None  # busted by the write
    finally:
        session.query(InteractionHistory).filter_by(user_key=uk).delete()
        session.commit()
        redis_client.delete(key)


def test_user_prompt_includes_dislikes_and_recency():
    from app.agent.loop import _build_user_prompt

    req = AgentRequest(pantry=["pasta"], disliked_ingredients=["mushroom"], cuisine_prefs=["italian"])
    recent = [{"id": 1, "title": "Tomato Garlic Pasta"}]
    prompt = _build_user_prompt(req, recent)
    assert "mushroom" in prompt
    assert "italian" in prompt
    assert "Tomato Garlic Pasta" in prompt
