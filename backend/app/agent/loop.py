"""Raw Anthropic tool-calling loop + validation/repair.

A hand-written `while stop_reason == "tool_use"` loop, deliberately NOT the SDK
tool-runner (which hides exactly the mechanics this stage exists to teach):
stop-reason handling, echoing the assistant content back, returning ALL tool
results in a single user message, the iteration cap, and requesting a
schema-validated final answer.

After the model produces a plan, a DETERMINISTIC validator (validator.py) checks
it against the DB. On a violation the loop feeds the violations back for up to
REPAIR_MAX_ATTEMPTS repair turns; if still invalid it returns a deterministic
fallback plan with degraded=true. Every run is logged to generation_events.
"""
from __future__ import annotations

import json
import logging
import time

from sqlalchemy.orm import Session

from app.agent.prompts import system_prompt
from app.agent.tools import anthropic_tools, call_tool
from app.agent.tracing import persist_trace
from app.agent.validator import validate_plan
from app.core.config import settings
from app.models import GenerationEvent
from app.schemas.agent import AgentRequest, AgentResult, MealPlanItem, MealPlanResponse
from app.services.ingredients import disliked_recipe_ids, resolve_pantry
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


def _usage(resp) -> tuple[int, int]:
    u = getattr(resp, "usage", None)
    if not u:
        return 0, 0
    return (getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0)


def _parse_plan(client, system: str, messages: list[dict]):
    """Returns (plan_or_none, input_tokens, output_tokens)."""
    try:
        parsed = client.messages.parse(
            model=settings.LLM_MODEL_MAIN,
            max_tokens=2048,
            system=system,
            messages=messages,
            output_format=MealPlanResponse,
        )
        uin, uout = _usage(parsed)
        return parsed.parsed_output, uin, uout
    except Exception as e:
        logger.warning("structuring failed: %s", e)
        return None, 0, 0


def deterministic_plan(session: Session, request: AgentRequest) -> MealPlanResponse:
    """Constraint-clean fallback: SQL retrieval applies the hard filters, so the
    resulting plan can never violate diet/allergen/time. Disliked ingredients
    aren't a hard filter (they're a soft preference), so instead of excluding
    them we demote them in ranking — they surface only if nothing clean fits."""
    resolved = resolve_pantry(session, request.pantry)
    candidates = fetch_candidates(
        session,
        resolved.ingredient_ids,
        diet=request.diet,
        exclude_allergens=request.exclude_allergens,
        limit=50,
    )
    disliked_ids = disliked_recipe_ids(
        session, [c.id for c in candidates], request.disliked_ingredients
    )
    ranked = rank(candidates, limit=request.limit, disliked_ids=disliked_ids)
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
    usage = {"in": 0, "out": 0}
    trace: list[dict] = []  # the single-engine trail (mirrors the graph's)

    def ms() -> int:
        return int((time.perf_counter() - t0) * 1000)

    def finish(node: str, **fields) -> None:
        """Append a run-summary event and persist the trail (no-op without session_id)."""
        trace.append({
            "node": node, "event_type": "summary",
            "tokens": usage["in"] + usage["out"], "latency_ms": ms(),
            "tool_calls": tool_calls, "iterations": iterations, **fields,
        })
        persist_trace(session, request.session_id, "single", trace)

    def degraded_no_plan(stop, error) -> AgentResult:
        _log_event(session, request, [], repaired=False, degraded=True, latency_ms=ms())
        finish("_run", degraded=True, stop_reason=stop, error=error)
        return AgentResult(
            plan=None, degraded=True, stop_reason=stop, iterations=iterations,
            tool_calls=tool_calls, input_tokens=usage["in"], output_tokens=usage["out"],
            error=error,
        )

    # --- tool loop ---------------------------------------------------------- #
    for iterations in range(1, max_iterations + 1):
        tcall = time.perf_counter()
        resp = client.messages.create(
            model=settings.LLM_MODEL_MAIN,
            max_tokens=2048,
            system=system,
            messages=messages,
            tools=anthropic_tools(),
            thinking={"type": "adaptive"},
        )
        uin, uout = _usage(resp)
        usage["in"] += uin
        usage["out"] += uout
        stop = resp.stop_reason
        trace.append({
            "node": "agent", "event_type": "llm", "iteration": iterations,
            "stop_reason": stop, "tokens": uin + uout,
            "latency_ms": int((time.perf_counter() - tcall) * 1000),
        })

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
                trace.append({
                    "node": f"tool:{getattr(block, 'name', '?')}",
                    "event_type": "tool_use", "is_error": is_error,
                })
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

    # --- structure + validate + repair -------------------------- #
    messages.append({"role": "user", "content": FINAL_INSTRUCTION})
    plan, uin, uout = _parse_plan(client, system, messages)
    usage["in"] += uin
    usage["out"] += uout
    if plan is None:
        return degraded_no_plan("end_turn", "no structured plan returned")

    violations = validate_plan(session, plan, request)
    trace.append({
        "node": "structure", "event_type": "llm",
        "tokens": uin + uout, "violations": len(violations),
    })
    repaired = False
    attempt = 0
    while violations and attempt < settings.REPAIR_MAX_ATTEMPTS:
        attempt += 1
        repaired = True
        messages.append({"role": "assistant", "content": plan.model_dump_json()})
        messages.append({"role": "user", "content": _repair_prompt(violations)})
        plan, uin, uout = _parse_plan(client, system, messages)
        usage["in"] += uin
        usage["out"] += uout
        if plan is None:
            trace.append({"node": "repair", "event_type": "llm", "attempt": attempt,
                          "tokens": uin + uout, "failed": True})
            break
        violations = validate_plan(session, plan, request)
        trace.append({"node": "repair", "event_type": "llm", "attempt": attempt,
                      "tokens": uin + uout, "violations": len(violations)})

    if plan is None or violations:
        fallback = deterministic_plan(session, request)
        _log_event(session, request, violations, repaired=repaired, degraded=True, latency_ms=ms())
        finish("_run", degraded=True, repaired=repaired, violations=len(violations))
        return AgentResult(
            plan=fallback, degraded=True, repaired=repaired, violations=violations,
            stop_reason="end_turn", iterations=iterations, tool_calls=tool_calls,
            input_tokens=usage["in"], output_tokens=usage["out"],
            error="plan failed validation after repair attempts",
        )

    _log_event(session, request, [], repaired=repaired, degraded=False, latency_ms=ms())
    finish("_run", degraded=False, repaired=repaired, violations=0)
    return AgentResult(
        plan=plan, degraded=False, repaired=repaired, violations=[],
        stop_reason="end_turn", iterations=iterations, tool_calls=tool_calls,
        input_tokens=usage["in"], output_tokens=usage["out"],
    )
