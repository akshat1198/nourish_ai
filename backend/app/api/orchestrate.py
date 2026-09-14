"""Orchestrator endpoint: POST /v1/orchestrate/plan.

Runs the LangGraph supervisor graph. With a session_id, the run is checkpointed
by thread_id so a follow-up turn continues without resending the pantry.
"""
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.tracing import persist_trace
from app.api.agent import _apply_profile, authorize_llm_call
from app.api.auth import get_current_user_key
from app.api.deps import get_session
from app.core.config import settings
from app.llm.client import is_enabled
from app.schemas.agent import (
    AgentRequest,
    AppliedConstraints,
    MealPlanItem,
    MealPlanResponse,
    OrchestrateResponse,
)
from app.services.profile import record_recommendations
from app.services.question_constraints import merge_into_request

router = APIRouter(prefix="/v1", tags=["orchestrate"])

# Graphs are built on first use, not at import. Importing app.orchestrator pulls
# in langchain_anthropic (~172 MB resident) and get_checkpointer() opens a
# Postgres pool -- at module scope both happen during boot, before uvicorn binds
# the port, on every deploy that never serves this endpoint. Same lazy-singleton
# shape as services.embedder.get_embedder().
_graphs: dict[str, object] = {}


def _graph(checkpointed: bool):
    key = "checkpointed" if checkpointed else "plain"
    if key not in _graphs:
        from app.orchestrator.checkpoint import get_checkpointer
        from app.orchestrator.graph import build_graph

        _graphs[key] = (
            build_graph(checkpointer=get_checkpointer()) if checkpointed else build_graph()
        )
    return _graphs[key]


@router.post("/orchestrate/plan", response_model=OrchestrateResponse)
def orchestrate(
    req: AgentRequest,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    if not settings.ORCHESTRATE_ENABLED:
        raise HTTPException(503, "The planner is turned off right now.")
    if not is_enabled():
        raise HTTPException(503, "orchestrator requires ANTHROPIC_API_KEY")
    try:
        from app.orchestrator.graph import invoke_graph
    except ImportError as e:
        # The runtime image can ship without langgraph/langchain-anthropic; say so
        # rather than 500ing on an import the deployment deliberately left out.
        raise HTTPException(503, f"orchestrator not available in this deployment: {e}")

    authorize_llm_call(req, user_key, "orchestrate")
    _apply_profile(session, req)
    # Read the hard constraints out of the question BEFORE retrieval, so "no
    # dairy" typed in prose reaches the SQL exclude and the validator, not just
    # the model's discretion. Without this the planner returned dairy recipes
    # for exactly that phrasing, with violations empty.
    applied = merge_into_request(req, req.question)
    # Per-turn fields reset each call; pantry/draft persist via the checkpoint.
    state_in = {"request": req.model_dump(), "repair_count": 0, "violations": [], "trace": []}

    t0 = time.perf_counter()
    if req.session_id:
        config = {"configurable": {"thread_id": req.session_id}}
        final, tin, tout = invoke_graph(_graph(True), state_in, config)
    else:
        final, tin, tout = invoke_graph(_graph(False), state_in)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    draft = final.get("draft", {"recipes": []})
    plan = MealPlanResponse(
        recipes=[MealPlanItem(**r) for r in draft["recipes"]],
        summary=final.get("summary", ""),
    )

    if req.user_key and plan.recipes:
        record_recommendations(session, req.user_key, [r.recipe_id for r in plan.recipes])

    # Persist this run's trail. A final summary row carries the run's
    # total tokens/latency so the traces endpoint has the headline numbers.
    trace = list(final.get("trace", []))
    trace.append({
        "node": "_run", "event_type": "summary",
        "tokens": tin + tout, "latency_ms": latency_ms,
        "degraded": final.get("degraded", False),
        "repair_count": final.get("repair_count", 0),
    })
    persist_trace(session, req.session_id, "graph", trace)

    return OrchestrateResponse(
        plan=plan,
        applied_constraints=AppliedConstraints(**applied),
        degraded=final.get("degraded", False),
        violations=final.get("violations", []),
        nutrition=final.get("nutrition", []),
        shopping_list=final.get("shopping_list", {}),
        repair_count=final.get("repair_count", 0),
        input_tokens=tin,
        output_tokens=tout,
        trace=final.get("trace", []),
    )
