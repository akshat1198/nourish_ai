"""Agent endpoint: POST /v1/agent/recommend."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.loop import run_agent
from app.api.auth import get_current_user_key, scope_session_id
from app.api.deps import get_session
from app.core.config import settings
from app.llm.client import LLMError, get_llm, is_enabled
from app.schemas.agent import AgentRequest, AgentResult
from app.services.profile import (
    load_profile,
    recent_recommended,
    record_recommendations,
)
from app.services.rate_limit import (
    RateLimitExceeded,
    RateLimitUnavailable,
    consume,
)

router = APIRouter(prefix="/v1", tags=["agent"])


def authorize_llm_call(req: AgentRequest, user_key: str, bucket: str) -> None:
    """Bind the request to the caller's identity and charge it to their quota.

    `AgentRequest.user_key` arrives from the request body, which nothing has
    verified. Both LLM endpoints reach profile data and recommendation history
    through it, so it is overwritten with the authenticated identity rather than
    trusted -- otherwise any caller could read and write any user's profile by
    naming them, on an endpoint that also spends money per call.
    """
    req.user_key = user_key
    # Everything downstream (checkpoint thread_id, persisted traces) reads this
    # field, so scoping it once here is what keeps sessions private.
    req.session_id = scope_session_id(user_key, req.session_id)
    try:
        consume(bucket, user_key, settings.AGENT_DAILY_LIMIT)
    except RateLimitExceeded as e:
        raise HTTPException(
            429, f"Daily limit reached ({e.limit} planning requests). Resets at UTC midnight."
        )
    except RateLimitUnavailable:
        # Deliberately fail closed -- see services/rate_limit.py.
        raise HTTPException(503, "Planning is unavailable right now. Try again shortly.")


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
def agent_recommend(
    req: AgentRequest,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    if not is_enabled():
        raise HTTPException(503, "agent requires ANTHROPIC_API_KEY")
    try:
        client = get_llm().raw()
    except LLMError as e:
        raise HTTPException(503, str(e))

    authorize_llm_call(req, user_key, "agent")
    _apply_profile(session, req)
    recent = recent_recommended(session, req.user_key) if req.user_key else []

    result = run_agent(session, req, client=client, recent_recipe_ids=recent)

    # Record what we recommended so future runs can avoid repeats.
    if req.user_key and result.plan and result.plan.recipes:
        record_recommendations(
            session, req.user_key, [r.recipe_id for r in result.plan.recipes]
        )
    return result
