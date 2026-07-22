"""Deterministic validator tests — DB-backed, no LLM."""
from sqlalchemy import select

from app.agent.validator import validate_plan
from app.models import Recipe
from app.schemas.agent import AgentRequest, MealPlanItem, MealPlanResponse
from app.tests.conftest import requires_db


def _plan(*recipe_ids):
    return MealPlanResponse(
        recipes=[MealPlanItem(recipe_id=i, title=f"r{i}", why="") for i in recipe_ids],
        summary="",
    )


def _recipe_by_title(session, title):
    return session.execute(select(Recipe).where(Recipe.title == title)).scalar_one()


def test_empty_plan_flagged():
    v = validate_plan(None, MealPlanResponse(recipes=[], summary=""), AgentRequest())
    assert v and v[0]["type"] == "empty_plan"


@requires_db
def test_clean_plan_passes(session):
    # Tomato Garlic Pasta is vegetarian; request vegetarian + no forbidden allergen.
    tgp = _recipe_by_title(session, "Tomato Garlic Pasta")
    v = validate_plan(session, _plan(tgp.id), AgentRequest(diet="vegetarian"))
    assert v == []


@requires_db
def test_allergen_violation_caught(session):
    # Tomato Garlic Pasta contains dairy (parmesan) + gluten; request excludes dairy.
    tgp = _recipe_by_title(session, "Tomato Garlic Pasta")
    v = validate_plan(session, _plan(tgp.id), AgentRequest(exclude_allergens=["dairy"]))
    assert any(x["type"] == "allergen" for x in v)


@requires_db
def test_diet_violation_caught(session):
    # A meat recipe is not vegan.
    stir = session.execute(
        select(Recipe).where(Recipe.title.like("Chicken Breast & %Stir-Fry")).limit(1)
    ).scalar_one()
    v = validate_plan(session, _plan(stir.id), AgentRequest(diet="vegan"))
    assert any(x["type"] == "diet" for x in v)


@requires_db
def test_time_violation_caught(session):
    slow = session.execute(
        select(Recipe).where(Recipe.time_minutes >= 45).limit(1)
    ).scalar_one()
    v = validate_plan(session, _plan(slow.id), AgentRequest(max_time_minutes=15))
    assert any(x["type"] == "time" for x in v)


def test_unknown_recipe_caught():
    v = validate_plan(_FakeSession(), _plan(999999), AgentRequest())
    assert any(x["type"] == "unknown_recipe" for x in v)


class _FakeSession:
    def get(self, model, pk):
        return None
