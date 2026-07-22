"""Saved-recipe endpoints. Owner-scoped by the authed user_key."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_key
from app.api.deps import get_session
from app.models import Recipe
from app.schemas.saved import SavedListOut, SaveIn
from app.services.saved import add_saved, list_saved, remove_saved

router = APIRouter(prefix="/v1", tags=["saved"])


@router.get("/saved", response_model=SavedListOut)
def get_saved(
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    return SavedListOut(recipes=list_saved(session, user_key))


@router.post("/saved", response_model=SavedListOut)
def save_recipe(
    body: SaveIn,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    if session.get(Recipe, body.recipe_id) is None:
        raise HTTPException(404, "recipe not found")
    add_saved(session, user_key, body.recipe_id)
    return SavedListOut(recipes=list_saved(session, user_key))


@router.delete("/saved/{recipe_id}", response_model=SavedListOut)
def unsave_recipe(
    recipe_id: int,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    remove_saved(session, user_key, recipe_id)
    return SavedListOut(recipes=list_saved(session, user_key))
