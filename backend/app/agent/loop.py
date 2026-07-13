"""Raw Anthropic tool-calling loop (Stage 3.2) — the learning centerpiece.

A hand-written `while stop_reason == "tool_use"` loop, deliberately NOT the SDK
tool-runner (which hides exactly the mechanics this stage exists to teach):
stop-reason handling, echoing the assistant content back, returning ALL tool
results in a single user message, the iteration cap, and requesting a
schema-validated final answer. The production shortcut is
`client.beta.messages.tool_runner`.

Validation + repair (LLM-04/05) land in Stage 3.3; here the loop just runs
tools and structures the answer.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.agent.tools import anthropic_tools, call_tool
from app.core.config import settings
from app.schemas.agent import AgentRequest, AgentResult
from app.schemas.agent import MealPlanResponse

logger = logging.getLogger(__name__)

SYSTEM = (
    "You are NourishAI, a recipe assistant. Given a user's pantry and request, "
    "use the tools to find recipes that fit, verify they respect any allergen or "
    "diet constraints, and suggest ingredient substitutions when they help. "
    "Prefer recipes that use more of the pantry. Call tools as needed; you can "
    "call several at once. When you have a final recommendation, stop calling "
    "tools and give a short answer — you'll then be asked to format it as JSON."
)

FINAL_INSTRUCTION = (
    "Now return your final recommendation as JSON matching the required schema. "
    "Use recipe_ids from the tool results. Do not call any more tools."
)


def _build_user_prompt(req: AgentRequest) -> str:
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
    if req.max_time_minutes is not None:
        parts.append(f"Max time: {req.max_time_minutes} minutes")
    parts.append(f"Recommend up to {req.limit} recipe(s).")
    return "\n".join(parts)


def _degraded(stop_reason: str, iterations: int, tool_calls: int, error: str) -> AgentResult:
    return AgentResult(
        plan=None,
        degraded=True,
        stop_reason=stop_reason,
        iterations=iterations,
        tool_calls=tool_calls,
        error=error,
    )


def run_agent(
    session: Session,
    request: AgentRequest,
    *,
    client,
    max_iterations: int = 8,
) -> AgentResult:
    """Drive the tool loop, then request a schema-validated MealPlanResponse.

    `client` is an anthropic.Anthropic-like object exposing messages.create and
    messages.parse — injected so tests can script it without real API calls.
    """
    messages: list[dict] = [{"role": "user", "content": _build_user_prompt(request)}]
    tool_calls = 0
    iterations = 0

    for iterations in range(1, max_iterations + 1):
        resp = client.messages.create(
            model=settings.LLM_MODEL_MAIN,
            max_tokens=2048,
            system=SYSTEM,
            messages=messages,
            tools=anthropic_tools(),
            thinking={"type": "adaptive"},
        )
        stop = resp.stop_reason

        if stop == "tool_use":
            # Echo the assistant content back verbatim (preserves thinking +
            # tool_use blocks the API requires on the next turn).
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                tool_calls += 1
                try:
                    output = call_tool(session, block.name, dict(block.input))
                    content, is_error = json.dumps(output), False
                except Exception as e:  # tool failure is data, not a crash
                    content, is_error = f"error: {e}", True
                    logger.warning("tool %s failed: %s", getattr(block, "name", "?"), e)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                        "is_error": is_error,
                    }
                )
            # ALL tool results go back in ONE user message.
            messages.append({"role": "user", "content": results})
            continue

        if stop == "refusal":
            return _degraded(stop, iterations, tool_calls, "model refused the request")
        if stop == "max_tokens":
            return _degraded(stop, iterations, tool_calls, "hit max_tokens")
        if stop == "end_turn":
            messages.append({"role": "assistant", "content": resp.content})
            break
    else:
        return _degraded("tool_use", max_iterations, tool_calls, "hit iteration cap")

    # Final turn: request the structured answer (no tools).
    messages.append({"role": "user", "content": FINAL_INSTRUCTION})
    try:
        parsed = client.messages.parse(
            model=settings.LLM_MODEL_MAIN,
            max_tokens=2048,
            system=SYSTEM,
            messages=messages,
            output_format=MealPlanResponse,
        )
        plan = parsed.parsed_output
    except Exception as e:
        logger.warning("final structuring failed: %s", e)
        return _degraded("end_turn", iterations, tool_calls, f"structuring failed: {e}")

    if plan is None:
        return _degraded("end_turn", iterations, tool_calls, "no structured plan returned")

    return AgentResult(
        plan=plan,
        degraded=False,
        stop_reason="end_turn",
        iterations=iterations,
        tool_calls=tool_calls,
    )
