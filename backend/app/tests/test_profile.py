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


def test_user_prompt_includes_dislikes_and_recency():
    from app.agent.loop import _build_user_prompt

    req = AgentRequest(pantry=["pasta"], disliked_ingredients=["mushroom"], cuisine_prefs=["italian"])
    recent = [{"id": 1, "title": "Tomato Garlic Pasta"}]
    prompt = _build_user_prompt(req, recent)
    assert "mushroom" in prompt
    assert "italian" in prompt
    assert "Tomato Garlic Pasta" in prompt
