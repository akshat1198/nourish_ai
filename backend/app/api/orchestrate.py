"""Orchestrator endpoint (Stage 4.2): POST /v1/orchestrate/plan.

Runs the LangGraph supervisor graph. Same request shape as the single agent, so
4.4 can compare them head to head.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.agent import _apply_profile
from app.api.deps import get_session
from app.llm.client import is_enabled
from app.orchestrator.graph import build_graph
from app.schemas.agent import (
    AgentRequest,
    MealPlanItem,
    MealPlanResponse,
    OrchestrateResponse,
)
from app.services.profile import record_recommendations

router = APIRouter(prefix="/v1", tags=["orchestrate"])


@router.post("/orchestrate/plan", response_model=OrchestrateResponse)
def orchestrate(req: AgentRequest, session: Session = Depends(get_session)):
    if not is_enabled():
        raise HTTPException(503, "orchestrator requires ANTHROPIC_API_KEY")

    _apply_profile(session, req)
    graph = build_graph()
    final = graph.invoke({"request": req.model_dump(), "repair_count": 0, "trace": []})

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
