"""Profile + feedback endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_key
from app.api.deps import get_session
from app.core.config import settings
from app.models import Recipe
from app.schemas.profile import (
    FeedbackIn,
    FeedbackStateOut,
    ProfileIn,
    ProfileOut,
    RecipeFeedback,
)
from app.services.personalization import invalidate_taste_cache
from app.services.profile import (
    feedback_state,
    load_profile,
    record_interaction,
    upsert_profile,
)

router = APIRouter(prefix="/v1", tags=["profile"])


def _enforce_owner(path_key: str, token_key: str) -> None:
    """In jwt mode, a user may only touch their own profile (path == token)."""
    if settings.AUTH_MODE == "jwt" and path_key != token_key:
        raise HTTPException(403, "cannot access another user's profile")


@router.get("/profile/{user_key}", response_model=ProfileOut)
def get_profile(
    user_key: str,
    session: Session = Depends(get_session),
    token_key: str = Depends(get_current_user_key),
):
    _enforce_owner(user_key, token_key)
    profile = load_profile(session, user_key)
    if profile is None:
        return ProfileOut(user_key=user_key)  # empty default
    return ProfileOut(
        user_key=profile.user_key,
        diet=profile.diet,
        allergens=profile.allergens,
        disliked_ingredients=profile.disliked_ingredients,
        cuisine_prefs=profile.cuisine_prefs,
    )


@router.put("/profile/{user_key}", response_model=ProfileOut)
def put_profile(
    user_key: str,
    body: ProfileIn,
    session: Session = Depends(get_session),
    token_key: str = Depends(get_current_user_key),
):
    _enforce_owner(user_key, token_key)
    profile = upsert_profile(session, user_key, body)
    return ProfileOut(
        user_key=profile.user_key,
        diet=profile.diet,
        allergens=profile.allergens,
        disliked_ingredients=profile.disliked_ingredients,
        cuisine_prefs=profile.cuisine_prefs,
    )


@router.post("/feedback")
def feedback(
    body: FeedbackIn,
    session: Session = Depends(get_session),
    token_key: str = Depends(get_current_user_key),
):
    _enforce_owner(body.user_key, token_key)
    if session.get(Recipe, body.recipe_id) is None:
        raise HTTPException(404, "recipe not found")
    record_interaction(session, body.user_key, body.recipe_id, body.action)
    # Any feedback write can change this user's taste vector inputs
    # — bust the cache so the next recommend reflects it immediately rather
    # than waiting out TASTE_CACHE_TTL.
    invalidate_taste_cache(body.user_key)
    return {"ok": True}


@router.get("/feedback/{user_key}", response_model=FeedbackStateOut)
def get_feedback(
    user_key: str,
    session: Session = Depends(get_session),
    token_key: str = Depends(get_current_user_key),
):
    """Derived current feedback (made / rating) per recipe this user touched."""
    _enforce_owner(user_key, token_key)
    state = feedback_state(session, user_key)
    return FeedbackStateOut(
        user_key=user_key,
        recipes={rid: RecipeFeedback(**s) for rid, s in state.items()},
    )
