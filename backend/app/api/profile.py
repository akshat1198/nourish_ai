"""Profile + feedback endpoints (AGENT-01/02, API-05)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models import Recipe
from app.schemas.profile import FeedbackIn, ProfileIn, ProfileOut
from app.services.profile import load_profile, record_interaction, upsert_profile

router = APIRouter(prefix="/v1", tags=["profile"])


@router.get("/profile/{user_key}", response_model=ProfileOut)
def get_profile(user_key: str, session: Session = Depends(get_session)):
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
def put_profile(user_key: str, body: ProfileIn, session: Session = Depends(get_session)):
    profile = upsert_profile(session, user_key, body)
    return ProfileOut(
        user_key=profile.user_key,
        diet=profile.diet,
        allergens=profile.allergens,
        disliked_ingredients=profile.disliked_ingredients,
        cuisine_prefs=profile.cuisine_prefs,
    )


@router.post("/feedback")
def feedback(body: FeedbackIn, session: Session = Depends(get_session)):
    if session.get(Recipe, body.recipe_id) is None:
        raise HTTPException(404, "recipe not found")
    record_interaction(session, body.user_key, body.recipe_id, body.action)
    return {"ok": True}
