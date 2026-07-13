"""Ingredient autocomplete (Stage 5): GET /v1/ingredients?q=

Prefix/substring match over the canonical vocabulary (~99 rows) and their
aliases, using the same `normalize` spine as pantry resolution so what the UI
offers is exactly what the backend can resolve. Small table -> filter in Python.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models import Ingredient
from app.schemas.ingredient import IngredientSuggestion
from app.services.ingredients import normalize

router = APIRouter(prefix="/v1", tags=["ingredients"])


@router.get("/ingredients", response_model=list[IngredientSuggestion])
def list_ingredients(
    q: str = Query("", max_length=64),
    limit: int = Query(12, ge=1, le=50),
    session: Session = Depends(get_session),
):
    qn = normalize(q)
    out: list[tuple[bool, IngredientSuggestion]] = []
    for ing in session.execute(select(Ingredient)).scalars():
        name_n = normalize(ing.name)
        if not qn or qn in name_n:
            out.append((name_n.startswith(qn), IngredientSuggestion(name=ing.name)))
            continue
        for alias in ing.aliases or []:
            if qn in normalize(alias):
                out.append(
                    (False, IngredientSuggestion(name=ing.name, matched_alias=alias))
                )
                break
    # prefix matches first, then alphabetical
    out.sort(key=lambda t: (not t[0], t[1].name))
    return [s for _, s in out[:limit]]
