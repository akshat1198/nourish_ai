"""Recommendations endpoint (API-01) — SQL and hybrid retrieval."""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.services.cache import get_cached, recommend_key, set_cached
from app.services.embedder import get_embedder
from app.services.fallback import apply_fallback
from app.services.ingredients import resolve_pantry
from app.services.pantry_text import parse_pantry_text
from app.services.ranking import annotate, rank
from app.services.retrieval import fetch_candidates, fetch_hybrid

router = APIRouter(prefix="/v1", tags=["recommendations"])

# Retrieve a wider pool than requested so ranking has room to reorder.
CANDIDATE_POOL = 50


@router.post("/recommendations", response_model=RecommendResponse)
def recommend(
    req: RecommendRequest,
    response: Response,
    session: Session = Depends(get_session),
    mode: str = Query("hybrid", pattern="^(sql|hybrid)$"),
):
    key = recommend_key({**req.model_dump(), "mode": mode})
    cached = get_cached(key)
    if cached is not None:
        response.headers["X-Cache"] = "hit"
        return RecommendResponse(**cached)

    # LLM-parse free-text pantry (fail-open) and merge into the ingredient list.
    parsed = parse_pantry_text(req.pantry_text) if req.pantry_text else []
    pantry = req.pantry + parsed
    resolved = resolve_pantry(session, pantry)

    if mode == "hybrid":
        # Query text for the vector arm: pantry terms + the raw free-text.
        query_str = " ".join(pantry + ([req.pantry_text] if req.pantry_text else []))
        query_vec = get_embedder().embed([query_str])[0] if query_str.strip() else []
        candidates = fetch_hybrid(
            session,
            resolved.ingredient_ids,
            query_vec,
            diet=req.diet,
            exclude_allergens=req.exclude_allergens,
            max_time=req.max_time_minutes,
            limit=CANDIDATE_POOL,
        )
        # Rank the full pool; apply_fallback trims to req.limit (it may need the
        # wider pool to find swap-eligible recipes).
        pool = annotate(candidates, limit=CANDIDATE_POOL)
    else:
        candidates = fetch_candidates(
            session,
            resolved.ingredient_ids,
            diet=req.diet,
            exclude_allergens=req.exclude_allergens,
            max_time=req.max_time_minutes,
            limit=CANDIDATE_POOL,
        )
        pool = rank(candidates, limit=CANDIDATE_POOL)

    fb_mode, explanation, results = apply_fallback(
        session, pool, resolved.ingredient_ids, limit=req.limit
    )
    payload = RecommendResponse(
        results=results,
        mode=fb_mode,
        explanation=explanation,
        unmatched_pantry=resolved.unmatched,
    )
    set_cached(key, payload.model_dump())
    response.headers["X-Cache"] = "miss"
    return payload
