"""Orchestrator endpoint (Stage 4.2-4.3): POST /v1/orchestrate/plan.

Runs the LangGraph supervisor graph. With a session_id, the run is checkpointed
by thread_id so a follow-up turn continues without resending the pantry.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.agent import _apply_profile
from app.api.deps import get_session
from app.llm.client import is_enabled
from app.orchestrator.checkpoint import get_checkpointer
from app.orchestrator.graph import build_graph
from app.schemas.agent import (
    AgentRequest,
    MealPlanItem,
    MealPlanResponse,
    OrchestrateResponse,
)
from app.services.profile import record_recommendations

router = APIRouter(prefix="/v1", tags=["orchestrate"])

# Compile once. The checkpointed graph persists PlanState per thread_id.
_plain_graph = build_graph()
_checkpointed_graph = build_graph(checkpointer=get_checkpointer())


@router.post("/orchestrate/plan", response_model=OrchestrateResponse)
def orchestrate(req: AgentRequest, session: Session = Depends(get_session)):
    if not is_enabled():
        raise HTTPException(503, "orchestrator requires ANTHROPIC_API_KEY")

    _apply_profile(session, req)
    # Per-turn fields reset each call; pantry/draft persist via the checkpoint.
    state_in = {"request": req.model_dump(), "repair_count": 0, "violations": [], "trace": []}

    if req.session_id:
        config = {"configurable": {"thread_id": req.session_id}}
        final = _checkpointed_graph.invoke(state_in, config)
    else:
        final = _plain_graph.invoke(state_in)

    draft = final.get("draft", {"recipes": []})
    plan = MealPlanResponse(
        recipes=[MealPlanItem(**r) for r in draft["recipes"]],
        summary=final.get("summary", ""),
    )

    if req.user_key and plan.recipes:
        record_recommendations(session, req.user_key, [r.recipe_id for r in plan.recipes])

    return OrchestrateResponse(
        plan=plan,
        degraded=final.get("degraded", False),
        violations=final.get("violations", []),
        nutrition=final.get("nutrition", []),
        shopping_list=final.get("shopping_list", {}),
        repair_count=final.get("repair_count", 0),
        trace=final.get("trace", []),
    )
