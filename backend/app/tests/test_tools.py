"""Tool registry tests (LLM-03; check_inventory/save_meal_plan added Stage 11).

The deterministic tools are exercised directly against the DB. search_recipes
is gated behind RUN_EMBEDDER_TESTS=1 because it loads the embedding model.
"""
import json
import os

import pytest
from sqlalchemy import select

from app.agent.tools import TOOLS, anthropic_tools, call_tool
from app.models import MealPlan, MealPlanItem, PantryItem, Recipe
from app.schemas.pantry import PantryItemIn
from app.services.pantry import replace_pantry
from app.tests.conftest import requires_db

runs_embedder = pytest.mark.skipif(
    os.getenv("RUN_EMBEDDER_TESTS") != "1",
    reason="set RUN_EMBEDDER_TESTS=1 (loads the embedding model)",
)


def test_registry_has_seven_tools():
    assert set(TOOLS) == {
        "search_recipes",
        "check_allergens",
        "find_substitutions",
        "estimate_nutrition",
        "build_shopping_list",
        "check_inventory",
        "save_meal_plan",
    }


def test_anthropic_tool_defs_are_strict_and_closed():
    defs = anthropic_tools()
    assert len(defs) == 7
    for d in defs:
        assert d["strict"] is True
        assert d["input_schema"]["additionalProperties"] is False
        assert d["input_schema"]["required"]  # each has required fields


@requires_db
def test_check_allergens(session):
    tgp = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    out = call_tool(session, "check_allergens", {"recipe_id": tgp.id, "allergens": ["dairy", "nuts"]})
    assert out["safe"] is False
    assert "dairy" in out["violations"]  # parmesan
    assert "nuts" not in out["violations"]
    assert json.dumps(out)  # JSON-serializable


@requires_db
def test_check_allergens_missing_recipe(session):
    out = call_tool(session, "check_allergens", {"recipe_id": 999999, "allergens": ["dairy"]})
    assert "error" in out


@requires_db
def test_find_substitutions_vegan(session):
    out = call_tool(session, "find_substitutions", {"ingredient": "chicken breast", "diet": "vegan"})
    uses = {s["use"] for s in out["substitutes"]}
    assert "tofu" in uses  # tofu enables vegan
    # every returned swap must enable vegan
    assert all("vegan" in s["enables_diets"] for s in out["substitutes"])
    assert json.dumps(out)


@requires_db
def test_find_substitutions_unknown(session):
    out = call_tool(session, "find_substitutions", {"ingredient": "unobtanium"})
    assert out["substitutes"] == []


@requires_db
def test_estimate_nutrition_scales(session):
    tgp = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    one = call_tool(session, "estimate_nutrition", {"recipe_id": tgp.id, "servings": 1})
    two = call_tool(session, "estimate_nutrition", {"recipe_id": tgp.id, "servings": 2})
    assert two["total"]["calories"] == pytest.approx(one["total"]["calories"] * 2, rel=0.01)
    assert json.dumps(two)


@requires_db
def test_build_shopping_list_tool(session):
    tgp = session.execute(
        select(Recipe).where(Recipe.title == "Tomato Garlic Pasta")
    ).scalar_one()
    out = call_tool(
        session, "build_shopping_list", {"recipe_ids": [tgp.id], "pantry": ["pasta"]}
    )
    names = {i["name"] for i in out["items"]}
    assert "pasta" not in names  # in pantry
    assert "garlic" in names
    assert json.dumps(out)


@requires_db
@runs_embedder
def test_search_recipes(session):
    out = call_tool(
        session, "search_recipes", {"pantry": ["pasta", "tomato", "garlic"], "limit": 3}
    )
    titles = [r["title"] for r in out["results"]]
    assert "Tomato Garlic Pasta" in titles
    assert json.dumps(out)


@requires_db
def test_check_inventory_returns_pantry(session):
    uk = "tool-test-inventory"
    session.query(PantryItem).filter_by(user_key=uk).delete()
    session.commit()
    try:
        replace_pantry(session, uk, [PantryItemIn(ingredient="garlic", is_staple=True)])
        out = call_tool(session, "check_inventory", {"user_key": uk})
        assert out["user_key"] == uk
        garlic = next(i for i in out["pantry"] if i["ingredient"] == "garlic")
        assert garlic["is_staple"] is True
        assert json.dumps(out)
    finally:
        session.query(PantryItem).filter_by(user_key=uk).delete()
        session.commit()


@requires_db
def test_save_meal_plan_writes_rows(session):
    uk = "tool-test-plan"
    ids = list(session.execute(select(Recipe.id).limit(2)).scalars())
    session.query(MealPlan).filter_by(user_key=uk).delete()
    session.commit()
    try:
        out = call_tool(
            session,
            "save_meal_plan",
            {"user_key": uk, "name": "T", "recipe_ids": ids + [999999]},
        )
        assert out["added"] == 2
        assert out["skipped"] == [999999]
        assert json.dumps(out)

        plan = session.execute(
            select(MealPlan).where(MealPlan.user_key == uk)
        ).scalar_one()
        assert plan.name == "T"
        item_count = session.execute(
            select(MealPlanItem).where(MealPlanItem.plan_id == plan.id)
        ).scalars().all()
        assert len(item_count) == 2
        assert {i.recipe_id for i in item_count} == set(ids)
    finally:
        session.query(MealPlan).filter_by(user_key=uk).delete()
        session.commit()
