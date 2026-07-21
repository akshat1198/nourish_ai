"""Persistent pantry endpoints (Stage 5): GET/PUT /v1/pantry.

Keyed by the authed identity (`get_current_user_key`): in disabled mode that's
the `X-User-Key` header; in jwt mode it's `google:{sub}` from the verified token.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_key
from app.api.deps import get_session
from app.models import Ingredient
from app.schemas.ingredient import IngredientSuggestion
from app.schemas.pantry import PantryReplaceIn, PantryResponse
from app.services.ingredient_groups import load_groups
from app.services.ingredients import normalize
from app.services.pantry import get_pantry, replace_pantry
from app.services.pantry_text import parse_pantry_text

router = APIRouter(prefix="/v1", tags=["pantry"])


class PantryParseIn(BaseModel):
    text: str = Field(..., max_length=1000)


class PantryParseResponse(BaseModel):
    recognized: list[IngredientSuggestion] = Field(default_factory=list)
    unmatched: list[str] = Field(default_factory=list)


@router.get("/pantry", response_model=PantryResponse)
def read_pantry(
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    return PantryResponse(items=get_pantry(session, user_key))


@router.post("/pantry/parse", response_model=PantryParseResponse)
def parse_pantry(
    body: PantryParseIn,
    session: Session = Depends(get_session),
):
    """Free-text → recognized pantry items (LLM parse + canonical resolve). Does
    NOT mutate the pantry; the client adds the recognized items via PUT /pantry.
    No auth needed — pure text → ingredient resolution."""
    names = parse_pantry_text(body.text)
    if not names:
        return PantryParseResponse(recognized=[], unmatched=[])

    # Resolve each parsed term to a single canonical/generic display item (mirrors
    # the autocomplete: generics preferred, no member expansion, deduped).
    index: dict[str, Ingredient] = {}
    for ing in session.execute(select(Ingredient)).scalars():
        index.setdefault(normalize(ing.name), ing)
        for alias in ing.aliases or []:
            index.setdefault(normalize(alias), ing)
    generics: dict[str, tuple[str, str]] = {}
    for g in load_groups():
        for key in (g["generic"], *g.get("aliases", [])):
            generics.setdefault(normalize(key), (g["generic"], g.get("category")))

    recognized: list[IngredientSuggestion] = []
    unmatched: list[str] = []
    seen: set[str] = set()
    for raw in names:
        n = normalize(raw)
        if n in generics:
            gname, cat = generics[n]
            if gname not in seen:
                seen.add(gname)
                recognized.append(IngredientSuggestion(name=gname, category=cat, is_group=True))
        elif n in index:
            ing = index[n]
            if ing.name not in seen:
                seen.add(ing.name)
                recognized.append(IngredientSuggestion(name=ing.name, category=ing.category))
        elif raw.strip():
            unmatched.append(raw.strip())
    return PantryParseResponse(recognized=recognized, unmatched=unmatched)


@router.put("/pantry", response_model=PantryResponse)
def write_pantry(
    body: PantryReplaceIn,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    items, unmatched = replace_pantry(session, user_key, body.items)
    return PantryResponse(items=items, unmatched=unmatched)
