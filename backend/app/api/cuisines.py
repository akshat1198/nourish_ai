"""GET /v1/cuisines (Stage 6.4) — the authored taxonomy + live per-node counts.

The frontend swaps its static taxonomy for this so the questionnaire can grey
out zero-count nodes and drill into regions that actually have recipes. One
call site by design; the taxonomy shape/labels come from app/core/cuisines.py.
"""
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.cuisines import CUISINE_TAXONOMY, label_for
from app.models import Recipe
from app.schemas.cuisine import CuisineCount

router = APIRouter(prefix="/v1", tags=["cuisines"])


@router.get("/cuisines", response_model=list[CuisineCount])
def list_cuisines(session: Session = Depends(get_session)):
    rows = session.execute(
        select(Recipe.cuisine, Recipe.region, func.count())
        .where(Recipe.cuisine.isnot(None))
        .group_by(Recipe.cuisine, Recipe.region)
    ).all()

    top_counts: dict[str, int] = defaultdict(int)
    child_counts: dict[tuple[str, str], int] = defaultdict(int)
    for cuisine, region, n in rows:
        top_counts[cuisine] += n
        if region:
            child_counts[(cuisine, region)] += n

    tree: list[CuisineCount] = []
    for top, children in CUISINE_TAXONOMY.items():
        tree.append(
            CuisineCount(
                id=top,
                label=label_for(top),
                count=top_counts.get(top, 0),
                children=[
                    CuisineCount(
                        id=f"{top}/{c}",
                        label=label_for(f"{top}/{c}"),
                        count=child_counts.get((top, c), 0),
                    )
                    for c in children
                ],
            )
        )
    return tree
