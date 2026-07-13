"""LangGraph supervisor graph (Stage 4.2, INT-04).

Supervisor + 4 specialist nodes over the typed PlanState, hand-built as a
StateGraph (not the prebuilt create_supervisor — the point is to learn the
state/edges/repair-loop mechanics). Two nodes are DELIBERATELY code, not LLMs:

    pantry_analyst      LLM (haiku)  — parse free-text pantry -> ingredient names
    recipe_planner      LLM (sonnet) — pick recipes from tool-fetched candidates
    safety_nutritionist CODE         — the Stage-3 validator + nutrition (no LLM)
    shopping_planner    CODE         — build_shopping_list (no LLM)
    supervisor          LLM (sonnet) — synthesize the final summary

The repair loop is a graph-native conditional edge: safety_nutritionist ->
recipe_planner while there are violations, capped at MAX_REPAIRS. Candidates
come from search_recipes, which already hard-filters diet/allergen/time, so the
planner picks from a constraint-clean set and violations are rare by design.

The three LLM calls are isolated in _*_llm helpers so tests can monkeypatch
them and exercise the compiled graph with no API or DB.
"""
from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph

from app.agent.tools import call_tool
from app.agent.validator import validate_plan
from app.core.config import settings
from app.db import SessionLocal
from app.orchestrator.state import PlanState
from app.schemas.agent import AgentRequest, DraftPlan, MealPlanItem, MealPlanResponse
from app.services.pantry_text import parse_pantry_text

MAX_REPAIRS = 2
CANDIDATE_LIMIT = 8


def _trace(state: PlanState, event: dict) -> list:
    return list(state.get("trace", [])) + [event]


# --------------------------------------------------------------------------- #
# LLM helpers (monkeypatched in tests)
# --------------------------------------------------------------------------- #
def _plan_llm(req: AgentRequest, candidates: list[dict], violations: list | None) -> DraftPlan:
    llm = ChatAnthropic(
        model=settings.LLM_MODEL_MAIN, max_tokens=1024
    ).with_structured_output(DraftPlan)
    cand_lines = "\n".join(
        f"{c['id']}: {c['title']} — diet={c['diet_labels']}, allergens={c['allergens']}, "
        f"{c['time_minutes']}min, missing {len(c['missing_ingredients'])}"
        for c in candidates
    )
    avoid = ""
    if violations:
        bad = ", ".join(str(v.get("recipe_id")) for v in violations if v.get("recipe_id"))
        avoid = f"\nA previous pick violated constraints — do NOT choose recipe_ids: {bad}."
    prompt = (
        f"Pick up to {req.limit} recipes for this request, using ONLY these candidates.\n"
        f"Constraints: diet={req.diet}, avoid_allergens={req.exclude_allergens}, "
        f"disliked={req.disliked_ingredients}, max_time={req.max_time_minutes}.{avoid}\n"
        f"Candidates:\n{cand_lines}\n"
        "Return recipe_id, title, and a one-line 'why' for each pick."
    )
    return llm.invoke(prompt)


def _summary_llm(req: AgentRequest, draft: dict, nutrition: list[dict]) -> str:
    llm = ChatAnthropic(model=settings.LLM_MODEL_MAIN, max_tokens=512)
    titles = ", ".join(r["title"] for r in draft["recipes"]) or "(none)"
    prompt = (
        f"Write one or two sentences summarizing this meal plan for the user's request "
        f"({req.question or 'recipe recommendations'}). Recipes: {titles}. "
        f"Nutrition per serving available for each. Be concise and friendly."
    )
    return llm.invoke(prompt).content


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def node_pantry_analyst(state: PlanState) -> dict:
    req = AgentRequest(**state["request"])
    parsed = parse_pantry_text(req.pantry_text) if req.pantry_text else []
    pantry = req.pantry + parsed
    return {"pantry": pantry, "trace": _trace(state, {"node": "pantry_analyst", "pantry": pantry})}


def node_recipe_planner(state: PlanState) -> dict:
    req = AgentRequest(**state["request"])
    is_repair = bool(state.get("violations"))
    repair_count = state.get("repair_count", 0) + (1 if is_repair else 0)
    with SessionLocal() as session:
        search = call_tool(
            session,
            "search_recipes",
            {
                "pantry": state["pantry"],
                "diet": req.diet,
                "exclude_allergens": req.exclude_allergens,
                "max_time_minutes": req.max_time_minutes,
                "limit": CANDIDATE_LIMIT,
            },
        )
    candidates = search["results"]
    draft = _plan_llm(req, candidates, state.get("violations") if is_repair else None)
    return {
        "candidates": candidates,
        "draft": draft.model_dump(),
        "repair_count": repair_count,
        "trace": _trace(state, {"node": "recipe_planner", "repair": is_repair, "n": len(draft.recipes)}),
    }


def node_safety_nutritionist(state: PlanState) -> dict:
    req = AgentRequest(**state["request"])
    plan = MealPlanResponse(
        recipes=[MealPlanItem(**r) for r in state["draft"]["recipes"]], summary=""
    )
    with SessionLocal() as session:
        violations = validate_plan(session, plan, req)
        nutrition = [
            call_tool(session, "estimate_nutrition", {"recipe_id": r["recipe_id"]})
            for r in state["draft"]["recipes"]
        ]
    return {
        "violations": violations,
        "nutrition": nutrition,
        "trace": _trace(state, {"node": "safety_nutritionist", "violations": len(violations)}),
    }


def route_after_safety(state: PlanState) -> str:
    if state.get("violations") and state.get("repair_count", 0) < MAX_REPAIRS:
        return "recipe_planner"
    return "shopping_planner"


def node_shopping_planner(state: PlanState) -> dict:
    with SessionLocal() as session:
        shopping = call_tool(
            session,
            "build_shopping_list",
            {
                "recipe_ids": [r["recipe_id"] for r in state["draft"]["recipes"]],
                "pantry": state["pantry"],
            },
        )
    return {"shopping_list": shopping, "trace": _trace(state, {"node": "shopping_planner"})}


def node_supervisor(state: PlanState) -> dict:
    req = AgentRequest(**state["request"])
    degraded = bool(state.get("violations"))  # survived the repair budget
    summary = _summary_llm(req, state["draft"], state.get("nutrition", []))
    return {
        "summary": summary,
        "degraded": degraded,
        "trace": _trace(state, {"node": "supervisor", "degraded": degraded}),
    }


# --------------------------------------------------------------------------- #
# Graph
# --------------------------------------------------------------------------- #
def build_graph(checkpointer=None):
    g = StateGraph(PlanState)
    g.add_node("pantry_analyst", node_pantry_analyst)
    g.add_node("recipe_planner", node_recipe_planner)
    g.add_node("safety_nutritionist", node_safety_nutritionist)
    g.add_node("shopping_planner", node_shopping_planner)
    g.add_node("supervisor", node_supervisor)

    g.add_edge(START, "pantry_analyst")
    g.add_edge("pantry_analyst", "recipe_planner")
    g.add_edge("recipe_planner", "safety_nutritionist")
    g.add_conditional_edges(
        "safety_nutritionist",
        route_after_safety,
        {"recipe_planner": "recipe_planner", "shopping_planner": "shopping_planner"},
    )
    g.add_edge("shopping_planner", "supervisor")
    g.add_edge("supervisor", END)
    return g.compile(checkpointer=checkpointer)
