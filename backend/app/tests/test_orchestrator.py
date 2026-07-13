"""LangGraph orchestrator tests (Stage 4.2) — compiled graph, no API or DB.

The three LLM helpers, call_tool, validate_plan, and SessionLocal are all
monkeypatched so this exercises graph routing (especially the repair edge).
"""
import pytest

from app.orchestrator import graph as g
from app.schemas.agent import DraftPlan, MealPlanItem


class _FakeCM:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


def _draft():
    return DraftPlan(recipes=[MealPlanItem(recipe_id=1, title="Tomato Garlic Pasta", why="fits")])


@pytest.fixture
def stub_graph(monkeypatch):
    monkeypatch.setattr(g, "SessionLocal", lambda: _FakeCM())
    monkeypatch.setattr(g, "parse_pantry_text", lambda text: [])
    monkeypatch.setattr(g, "_plan_llm", lambda req, cands, viol: _draft())
    monkeypatch.setattr(g, "_summary_llm", lambda req, draft, nutr: "A quick pasta.")

    def fake_call_tool(session, name, args):
        if name == "search_recipes":
            return {"results": [
                {"id": 1, "title": "Tomato Garlic Pasta", "diet_labels": ["vegetarian"],
                 "allergens": [], "time_minutes": 25, "missing_ingredients": []}
            ], "unmatched_pantry": []}
        if name == "estimate_nutrition":
            return {"recipe_id": 1, "total": {"calories": 500}}
        if name == "build_shopping_list":
            return {"items": [{"name": "garlic"}]}
        return {}

    monkeypatch.setattr(g, "call_tool", fake_call_tool)


def test_happy_path_runs_all_nodes_once(stub_graph, monkeypatch):
    monkeypatch.setattr(g, "validate_plan", lambda s, p, r: [])  # always clean
    graph = g.build_graph()
    final = graph.invoke({"request": {"pantry": ["pasta"]}, "repair_count": 0, "trace": []})

    nodes = [t["node"] for t in final["trace"]]
    assert nodes == [
        "pantry_analyst", "recipe_planner", "safety_nutritionist",
        "shopping_planner", "supervisor",
    ]
    assert final["degraded"] is False
    assert final["draft"]["recipes"][0]["recipe_id"] == 1
    assert final["summary"] == "A quick pasta."
    assert final["shopping_list"]["items"]


def test_repair_edge_fires_then_recovers(stub_graph, monkeypatch):
    # violations on the first safety pass, clean on the second -> planner runs twice.
    verdicts = iter([[{"recipe_id": 1, "type": "allergen", "detail": "dairy"}], []])
    monkeypatch.setattr(g, "validate_plan", lambda s, p, r: next(verdicts))
    graph = g.build_graph()
    final = graph.invoke({"request": {"pantry": ["pasta"], "exclude_allergens": ["dairy"]},
                          "repair_count": 0, "trace": []})

    nodes = [t["node"] for t in final["trace"]]
    assert nodes.count("recipe_planner") == 2  # repair edge fired
    assert nodes.count("safety_nutritionist") == 2
    assert final["repair_count"] == 1
    assert final["degraded"] is False  # recovered on the repair


def test_repairs_exhausted_marks_degraded(stub_graph, monkeypatch):
    monkeypatch.setattr(
        g, "validate_plan",
        lambda s, p, r: [{"recipe_id": 1, "type": "allergen", "detail": "dairy"}],  # always bad
    )
    graph = g.build_graph()
    final = graph.invoke({"request": {"pantry": ["pasta"], "exclude_allergens": ["dairy"]},
                          "repair_count": 0, "trace": []})

    nodes = [t["node"] for t in final["trace"]]
    # planner runs MAX_REPAIRS+1 times (initial + 2 repairs), then proceeds.
    assert nodes.count("recipe_planner") == g.MAX_REPAIRS + 1
    assert final["repair_count"] == g.MAX_REPAIRS
    assert final["degraded"] is True
    assert final["violations"]  # reported
