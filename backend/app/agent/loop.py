"""Raw Anthropic tool-calling loop + validation/repair (Stage 3.2 + 3.3).

A hand-written `while stop_reason == "tool_use"` loop, deliberately NOT the SDK
tool-runner (which hides exactly the mechanics this stage exists to teach):
stop-reason handling, echoing the assistant content back, returning ALL tool
results in a single user message, the iteration cap, and requesting a
schema-validated final answer.

After the model produces a plan, a DETERMINISTIC validator (validator.py) checks
it against the DB. On a violation the loop feeds the violations back for up to
REPAIR_MAX_ATTEMPTS repair turns; if still invalid it returns a deterministic
Stage-1 plan with degraded=true. Every run is logged to generation_events.
"""
from __future__ import annotations

import json
import logging
import time

from sqlalchemy.orm import Session

from app.agent.prompts import system_prompt
from app.agent.tools import anthropic_tools, call_tool
from app.agent.validator import validate_plan
from app.core.config import settings
from app.models import GenerationEvent
from app.schemas.agent import AgentRequest, AgentResult, MealPlanItem, MealPlanResponse
from app.services.ingredients import resolve_pantry
from app.services.ranking import rank
from app.services.retrieval import fetch_candidates

logger = logging.getLogger(__name__)

FINAL_INSTRUCTION = (
    "Now return your final recommendation as JSON matching the required schema. "
    "Use recipe_ids from the tool results. Do not call any more tools."
)


def _build_user_prompt(req: AgentRequest, recent: list[dict] | None = None) -> str:
    parts = []
    if req.pantry:
        parts.append(f"Pantry: {', '.join(req.pantry)}")
    if req.pantry_text:
        parts.append(f"Pantry (free text): {req.pantry_text}")
    if req.question:
        parts.append(f"Request: {req.question}")
    if req.diet:
        parts.append(f"Diet: {req.diet}")
    if req.exclude_allergens:
        parts.append(f"Avoid allergens: {', '.join(req.exclude_allergens)}")
    if req.disliked_ingredients:
        parts.append(
            f"Never use these disliked ingredients: {', '.join(req.disliked_ingredients)}"
        )
    if req.cuisine_prefs:
        parts.append(f"Preferred cuisines (soft): {', '.join(req.cuisine_prefs)}")
    if req.max_time_minutes is not None:
        parts.append(f"Max time: {req.max_time_minutes} minutes")
    if recent:
        titles = ", ".join(r["title"] for r in recent)
        parts.append(
            f"Recently recommended to this user (avoid repeating unless clearly "
            f"the best fit): {titles}"
        )
    parts.append(f"Recommend up to {req.limit} recipe(s).")
    return "\n".join(parts)


def _repair_prompt(violations: list[dict]) -> str:
    lines = "\n".join(f"- recipe {v.get('recipe_id', '?')}: {v['detail']}" for v in violations)
    return (
        "Your recommendation violated these constraints (verified against our "
        f"database):\n{lines}\n\n"
        "Replace or remove the offending recipes and return corrected JSON "
        "matching the schema. Do not call any tools."
    )


def _parse_plan(client, system: str, messages: list[dict]):
    try:
        parsed = client.messages.parse(
            model=settings.LLM_MODEL_MAIN,
            max_tokens=2048,
            system=system,
            messages=messages,
            output_format=MealPlanResponse,
        )
        return parsed.parsed_output
    except Exception as e:
        logger.warning("structuring failed: %s", e)
        return None


def deterministic_plan(session: Session, request: AgentRequest) -> MealPlanResponse:
    """Constraint-clean fallback: SQL retrieval applies the hard filters, so the
    resulting plan can never violate diet/allergen/time."""
    resolved = resolve_pantry(session, request.pantry)
    candidates = fetch_candidates(
        session,
        resolved.ingredient_ids,
        diet=request.diet,
        exclude_allergens=request.exclude_allergens,
        max_time=request.max_time_minutes,
        limit=50,
    )
    ranked = rank(candidates, limit=request.limit)
    items = [MealPlanItem(recipe_id=r.id, title=r.title, why=r.why) for r in ranked]
    return MealPlanResponse(
        recipes=items,
        summary="Deterministic fallback honoring your constraints (the AI plan "
        "could not be validated).",
    )


def _log_event(
    session, request, violations, *, repaired, degraded, latency_ms
) -> None:
    if session is None:
        return
    try:
        session.add(
            GenerationEvent(
                user_key=request.user_key,
                prompt_version=settings.PROMPT_VERSION,
                model=settings.LLM_MODEL_MAIN,
                violations=violations,
                repaired=repaired,
                degraded=degraded,
                latency_ms=latency_ms,
            )
        )
        session.commit()
    except Exception as e:  # logging must never break the response
        session.rollback()
        logger.warning("failed to log generation_event: %s", e)


def run_agent(
    session: Session,
    request: AgentRequest,
    *,
    client,
    recent_recipe_ids: list[dict] | None = None,
    max_iterations: int = 8,
) -> AgentResult:
    t0 = time.perf_counter()
    system = system_prompt()
    messages: list[dict] = [
        {"role": "user", "content": _build_user_prompt(request, recent_recipe_ids)}
    ]
    tool_calls = 0
    iterations = 0

    def ms() -> int:
        return int((time.perf_counter() - t0) * 1000)

    def degraded_no_plan(stop, error) -> AgentResult:
        _log_event(session, request, [], repaired=False, degraded=True, latency_ms=ms())
        return AgentResult(
            plan=None, degraded=True, stop_reason=stop, iterations=iterations,
            tool_calls=tool_calls, error=error,
        )

    # --- tool loop ---------------------------------------------------------- #
    for iterations in range(1, max_iterations + 1):
        resp = client.messages.create(
            model=settings.LLM_MODEL_MAIN,
            max_tokens=2048,
            system=system,
            messages=messages,
            tools=anthropic_tools(),
            thinking={"type": "adaptive"},
        )
        stop = resp.stop_reason

        if stop == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                tool_calls += 1
                try:
                    output = call_tool(session, block.name, dict(block.input))
                    content, is_error = json.dumps(output), False
                except Exception as e:
                    content, is_error = f"error: {e}", True
                    logger.warning("tool %s failed: %s", getattr(block, "name", "?"), e)
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id,
                     "content": content, "is_error": is_error}
                )
            messages.append({"role": "user", "content": results})
            continue

        if stop == "refusal":
            return degraded_no_plan(stop, "model refused the request")
        if stop == "max_tokens":
            return degraded_no_plan(stop, "hit max_tokens")
        if stop == "end_turn":
            messages.append({"role": "assistant", "content": resp.content})
            break
    else:
        return degraded_no_plan("tool_use", "hit iteration cap")

    # --- structure + validate + repair (LLM-04/05) -------------------------- #
    messages.append({"role": "user", "content": FINAL_INSTRUCTION})
    plan = _parse_plan(client, system, messages)
    if plan is None:
        return degraded_no_plan("end_turn", "no structured plan returned")

    violations = validate_plan(session, plan, request)
    repaired = False
    attempt = 0
    while violations and attempt < settings.REPAIR_MAX_ATTEMPTS:
        attempt += 1
        repaired = True
        messages.append({"role": "assistant", "content": plan.model_dump_json()})
        messages.append({"role": "user", "content": _repair_prompt(violations)})
        plan = _parse_plan(client, system, messages)
        if plan is None:
            break
        violations = validate_plan(session, plan, request)

    if plan is None or violations:
        fallback = deterministic_plan(session, request)
        _log_event(session, request, violations, repaired=repaired, degraded=True, latency_ms=ms())
        return AgentResult(
            plan=fallback, degraded=True, repaired=repaired, violations=violations,
            stop_reason="end_turn", iterations=iterations, tool_calls=tool_calls,
            error="plan failed validation after repair attempts",
        )

    _log_event(session, request, [], repaired=repaired, degraded=False, latency_ms=ms())
    return AgentResult(
        plan=plan, degraded=False, repaired=repaired, violations=[],
        stop_reason="end_turn", iterations=iterations, tool_calls=tool_calls,
    )
