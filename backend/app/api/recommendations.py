"""Recommendations endpoint (API-01)."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.services.cache import get_cached, recommend_key, set_cached
from app.services.ingredients import resolve_pantry
from app.services.ranking import rank
from app.services.retrieval import fetch_candidates

router = APIRouter(prefix="/v1", tags=["recommendations"])

# Retrieve a wider pool than requested so ranking has room to reorder.
CANDIDATE_POOL = 50


@router.post("/recommendations", response_model=RecommendResponse)
def recommend(
    req: RecommendRequest,
    response: Response,
    session: Session = Depends(get_session),
):
    key = recommend_key(req.model_dump())
    cached = get_cached(key)
    if cached is not None:
        response.headers["X-Cache"] = "hit"
        return RecommendResponse(**cached)

    resolved = resolve_pantry(session, req.pantry)
    candidates = fetch_candidates(
        session,
        resolved.ingredient_ids,
        diet=req.diet,
        exclude_allergens=req.exclude_allergens,
        max_time=req.max_time_minutes,
        limit=CANDIDATE_POOL,
    )
    results = rank(candidates, limit=req.limit)
    payload = RecommendResponse(results=results, unmatched_pantry=resolved.unmatched)

    set_cached(key, payload.model_dump())
    response.headers["X-Cache"] = "miss"
    return payload
