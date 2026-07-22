"""Ingredient autocomplete: GET /v1/ingredients?q=

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
from app.services.ingredient_groups import load_groups
from app.services.ingredients import normalize

router = APIRouter(prefix="/v1", tags=["ingredients"])


def _matching_groups(qn: str) -> list[IngredientSuggestion]:
    """Generic groups whose name or an alias matches the query, offered first so
    a user can pick "chicken" instead of committing to one specific cut."""
    hits: list[IngredientSuggestion] = []
    for g in load_groups():
        keys = [g["generic"], *g.get("aliases", [])]
        if not qn or any(qn in normalize(k) for k in keys):
            hits.append(
                IngredientSuggestion(
                    name=g["generic"],
                    category=g.get("category"),
                    is_group=True,
                    members=g.get("members"),
                )
            )
    return hits


@router.get("/ingredients", response_model=list[IngredientSuggestion])
def list_ingredients(
    q: str = Query("", max_length=64),
    limit: int = Query(12, ge=1, le=50),
    session: Session = Depends(get_session),
):
    qn = normalize(q)
    groups = _matching_groups(qn)
    out: list[tuple[bool, IngredientSuggestion]] = []
    for ing in session.execute(select(Ingredient)).scalars():
        name_n = normalize(ing.name)
        if not qn or qn in name_n:
            out.append(
                (name_n.startswith(qn),
                 IngredientSuggestion(name=ing.name, category=ing.category))
            )
            continue
        for alias in ing.aliases or []:
            if qn in normalize(alias):
                out.append(
                    (False, IngredientSuggestion(
                        name=ing.name, category=ing.category, matched_alias=alias))
                )
                break
    # prefix matches first, then alphabetical
    out.sort(key=lambda t: (not t[0], t[1].name))
    # Generics lead (the broader, less-restrictive pick), then the ranked singles.
    return (groups + [s for _, s in out])[:limit]
