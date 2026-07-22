"""Agent endpoint: POST /v1/agent/recommend."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.loop import run_agent
from app.api.deps import get_session
from app.llm.client import LLMError, get_llm, is_enabled
from app.schemas.agent import AgentRequest, AgentResult
from app.services.profile import (
    load_profile,
    recent_recommended,
    record_recommendations,
)

router = APIRouter(prefix="/v1", tags=["agent"])


def _apply_profile(session: Session, req: AgentRequest) -> None:
    """Fill unset constraints from the user's saved profile.

    Explicit request values win; the profile only fills what wasn't given.
    disliked_ingredients and cuisine_prefs always merge in from the profile.
    """
    if not req.user_key:
        return
    profile = load_profile(session, req.user_key)
    if profile is None:
        return
    if req.diet is None:
        req.diet = profile.diet
    if not req.exclude_allergens:
        req.exclude_allergens = list(profile.allergens or [])
    if not req.disliked_ingredients:
        req.disliked_ingredients = list(profile.disliked_ingredients or [])
    if not req.cuisine_prefs:
        req.cuisine_prefs = list(profile.cuisine_prefs or [])


@router.post("/agent/recommend", response_model=AgentResult)
def agent_recommend(req: AgentRequest, session: Session = Depends(get_session)):
    if not is_enabled():
        raise HTTPException(503, "agent requires ANTHROPIC_API_KEY")
    try:
        client = get_llm().raw()
    except LLMError as e:
        raise HTTPException(503, str(e))

    _apply_profile(session, req)
    recent = recent_recommended(session, req.user_key) if req.user_key else []

    result = run_agent(session, req, client=client, recent_recipe_ids=recent)

    # Record what we recommended so future runs can avoid repeats.
    if req.user_key and result.plan and result.plan.recipes:
        record_recommendations(
            session, req.user_key, [r.recipe_id for r in result.plan.recipes]
        )
    return result
