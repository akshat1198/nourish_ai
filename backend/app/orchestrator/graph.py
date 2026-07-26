"""LangGraph supervisor graph.

Supervisor + 4 specialist nodes over the typed PlanState, hand-built as a
StateGraph (not the prebuilt create_supervisor — the point is to learn the
state/edges/repair-loop mechanics). Two nodes are DELIBERATELY code, not LLMs:

    pantry_analyst      LLM (haiku)  — parse free-text pantry -> ingredient names
    recipe_planner      LLM (sonnet) — pick recipes from tool-fetched candidates
    safety_nutritionist CODE         — the validator + nutrition (no LLM)
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

import logging
import time

from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph

try:  # captures token usage across all langchain LLM calls in one run
    from langchain_core.callbacks import get_usage_metadata_callback
except Exception:  # pragma: no cover - older langchain-core
    get_usage_metadata_callback = None

from app.agent.tools import call_tool
from app.agent.validator import validate_plan
from app.core.config import settings
from app.db import SessionLocal
from app.orchestrator.state import PlanState
from app.schemas.agent import AgentRequest, DraftPlan, MealPlanItem, MealPlanResponse
from app.services.pantry_text import parse_pantry_text

logger = logging.getLogger(__name__)

MAX_REPAIRS = 2
CANDIDATE_LIMIT = 8


def _trace(state: PlanState, event: dict) -> list:
    return list(state.get("trace", [])) + [event]


# --------------------------------------------------------------------------- #
# LLM helpers (monkeypatched in tests)
# --------------------------------------------------------------------------- #
def _chat(max_tokens: int) -> ChatAnthropic:
    """ChatAnthropic with a bounded timeout + retry budget so a stalled request
    fails fast instead of hanging the graph forever (the raw client sets
    the same timeout via the anthropic SDK; langchain defaults to None = infinite)."""
    return ChatAnthropic(
        model=settings.LLM_MODEL_MAIN,
        max_tokens=max_tokens,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=2,
    )


def _plan_llm(
    req: AgentRequest,
    candidates: list[dict],
    violations: list | None,
    prior_recipes: list | None = None,
) -> DraftPlan:
    # json_schema (native structured output) is more reliable than tool-calling
    # for nested-list schemas, which occasionally get stringified.
    llm = _chat(1024).with_structured_output(DraftPlan, method="json_schema")
    cand_lines = "\n".join(
        f"{c['id']}: {c['title']} — diet={c['diet_labels']}, allergens={c['allergens']}, "
        f"missing {len(c['missing_ingredients'])}"
        for c in candidates
    )
    context = ""
    if violations:
        bad = ", ".join(str(v.get("recipe_id")) for v in violations if v.get("recipe_id"))
        context = f"\nA previous pick violated constraints — do NOT choose recipe_ids: {bad}."
    elif prior_recipes:  # a refinement on a continued session
        titles = ", ".join(r["title"] for r in prior_recipes)
        context = (
            f"\nThe user was previously recommended: {titles}. They now say: "
            f"'{req.question}'. Adjust your picks to honor this refinement."
        )
    prompt = (
        f"Pick up to {req.limit} recipes for this request, using ONLY these candidates.\n"
        f"Constraints: diet={req.diet}, avoid_allergens={req.exclude_allergens}, "
        f"disliked={req.disliked_ingredients}.{context}\n"
        f"Candidates:\n{cand_lines}\n"
        "Return recipe_id, title, and a one-line 'why' for each pick."
    )
    return llm.invoke(prompt)


def _summary_llm(req: AgentRequest, draft: dict, nutrition: list[dict]) -> str:
    llm = _chat(512)
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
    t0 = time.perf_counter()
    req = AgentRequest(**state["request"])
    if req.pantry or req.pantry_text:
        parsed = parse_pantry_text(req.pantry_text) if req.pantry_text else []
        pantry = req.pantry + parsed
    else:
        # Refinement turn: no pantry resent — keep the checkpointed one.
        pantry = state.get("pantry", [])
    return {
        "pantry": pantry,
        "trace": _trace(state, {
            "node": "pantry_analyst", "event_type": "node",
            "latency_ms": int((time.perf_counter() - t0) * 1000), "pantry": pantry,
        }),
    }


def node_recipe_planner(state: PlanState) -> dict:
    t0 = time.perf_counter()
    req = AgentRequest(**state["request"])
    is_repair = bool(state.get("violations"))
    repair_count = state.get("repair_count", 0) + (1 if is_repair else 0)
    # A prior draft with no active violations => this is a refinement turn.
    prior = state.get("draft", {}).get("recipes", []) if not is_repair else None
    with SessionLocal() as session:
        search = call_tool(
            session,
            "search_recipes",
            {
                "pantry": state["pantry"],
                "diet": req.diet,
                "exclude_allergens": req.exclude_allergens,
                "limit": CANDIDATE_LIMIT,
            },
        )
    candidates = search["results"]
    try:
        draft = _plan_llm(
            req, candidates, state.get("violations") if is_repair else None, prior_recipes=prior
        )
    except Exception as e:  # never let an LLM formatting glitch crash the graph
        logger.warning("recipe_planner LLM failed, using top candidates: %s", e)
        bad = {v.get("recipe_id") for v in (state.get("violations") or [])}
        clean = [c for c in candidates if c["id"] not in bad]
        draft = DraftPlan(
            recipes=[
                MealPlanItem(recipe_id=c["id"], title=c["title"], why="top match for your pantry")
                for c in clean[: req.limit]
            ]
        )
    return {
        "candidates": candidates,
        "draft": draft.model_dump(),
        "repair_count": repair_count,
        "trace": _trace(state, {
            "node": "recipe_planner", "event_type": "llm",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "repair": is_repair, "n": len(draft.recipes),
        }),
    }


def node_safety_nutritionist(state: PlanState) -> dict:
    t0 = time.perf_counter()
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
        "trace": _trace(state, {
            "node": "safety_nutritionist", "event_type": "node",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "violations": len(violations),
        }),
    }


def route_after_safety(state: PlanState) -> str:
    if state.get("violations") and state.get("repair_count", 0) < MAX_REPAIRS:
        return "recipe_planner"
    return "shopping_planner"


def node_shopping_planner(state: PlanState) -> dict:
    t0 = time.perf_counter()
    with SessionLocal() as session:
        shopping = call_tool(
            session,
            "build_shopping_list",
            {
                "recipe_ids": [r["recipe_id"] for r in state["draft"]["recipes"]],
                "pantry": state["pantry"],
            },
        )
    return {
        "shopping_list": shopping,
        "trace": _trace(state, {
            "node": "shopping_planner", "event_type": "node",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }),
    }


def node_supervisor(state: PlanState) -> dict:
    t0 = time.perf_counter()
    req = AgentRequest(**state["request"])
    degraded = bool(state.get("violations"))  # survived the repair budget
    try:
        summary = _summary_llm(req, state["draft"], state.get("nutrition", []))
    except Exception as e:  # a summary hiccup must not sink a valid plan
        logger.warning("supervisor summary LLM failed, using a plain summary: %s", e)
        titles = ", ".join(r["title"] for r in state["draft"]["recipes"]) or "your request"
        summary = f"Here are {len(state['draft']['recipes'])} recipe(s) for you: {titles}."
    return {
        "summary": summary,
        "degraded": degraded,
        "trace": _trace(state, {
            "node": "supervisor", "event_type": "llm",
            "latency_ms": int((time.perf_counter() - t0) * 1000), "degraded": degraded,
        }),
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


def invoke_graph(graph, state_in: dict, config: dict | None = None) -> tuple[dict, int, int]:
    """Invoke a compiled graph, returning (final_state, input_tokens, output_tokens).

    Token usage is aggregated across every langchain LLM call in the run via
    get_usage_metadata_callback — so the comparative eval and the endpoint can
    report graph cost without threading usage through PlanState. (pantry_analyst
    parses free text through the raw SDK, not langchain; the eval set uses
    structured pantries so that call doesn't fire — see run_agent's --engine graph.)
    """
    if get_usage_metadata_callback is None:
        final = graph.invoke(state_in, config) if config else graph.invoke(state_in)
        return final, 0, 0
    with get_usage_metadata_callback() as cb:
        final = graph.invoke(state_in, config) if config else graph.invoke(state_in)
    tin = sum(v.get("input_tokens", 0) for v in cb.usage_metadata.values())
    tout = sum(v.get("output_tokens", 0) for v in cb.usage_metadata.values())
    return final, tin, tout
