"""Recommendations endpoint (API-01) — SQL and hybrid retrieval."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.config import nutrition_goal_label
from app.core.cuisines import VALID_CUISINE_IDS
from app.schemas.recommend import RankedRecipe, RecommendRequest, RecommendResponse
from app.services.cache import get_cached, recommend_key, set_cached
from app.services.embedder import get_embedder
from app.services.fallback import apply_fallback
from app.services.ingredients import disliked_recipe_ids, resolve_pantry
from app.services.pantry_text import parse_pantry_text
from app.services.ranking import annotate, rank
from app.services.retrieval import fetch_candidates, fetch_hybrid

router = APIRouter(prefix="/v1", tags=["recommendations"])

# Retrieve a wider pool than requested so ranking has room to reorder.
CANDIDATE_POOL = 50


def _relaxed_explanation(dropped_nutrition: list[str], dropped_other: bool) -> str:
    """Message for the 'relaxed' mode: name what we set aside. Diet and allergen
    limits are never relaxed, so the closest matches are still safe to eat."""
    parts: list[str] = []
    if dropped_nutrition:
        goals = ", ".join(nutrition_goal_label(g) for g in dropped_nutrition)
        parts.append(f"the {goals} goal" + ("s" if len(dropped_nutrition) > 1 else ""))
    if dropped_other:
        parts.append("some of your other filters")
    what = " and ".join(parts) if parts else "some filters"
    return (
        f"No recipe fully matched {what} with your pantry — showing the closest "
        "matches instead. Your diet and allergen limits are still applied."
    )


@router.post("/recommendations", response_model=RecommendResponse)
def recommend(
    req: RecommendRequest,
    response: Response,
    session: Session = Depends(get_session),
    mode: str = Query("hybrid", pattern="^(sql|hybrid)$"),
):
    bad = [c for c in req.cuisines if c not in VALID_CUISINE_IDS]
    if bad:
        raise HTTPException(422, f"unknown cuisine id(s): {', '.join(bad)}")

    key = recommend_key({**req.model_dump(), "mode": mode})
    cached = get_cached(key)
    if cached is not None:
        response.headers["X-Cache"] = "hit"
        return RecommendResponse(**cached)

    # LLM-parse free-text pantry (fail-open) and merge into the ingredient list.
    parsed = parse_pantry_text(req.pantry_text) if req.pantry_text else []
    pantry = req.pantry + parsed
    resolved = resolve_pantry(session, pantry)

    query_vec: list[float] = []
    if mode == "hybrid":
        # Query text for the vector arm: pantry terms + the raw free-text.
        query_str = " ".join(pantry + ([req.pantry_text] if req.pantry_text else []))
        query_vec = get_embedder().embed([query_str])[0] if query_str.strip() else []

    def run(
        *,
        nutrition_goals: list[str],
        cuisines: list[str],
        meal_type: Optional[str],
        max_time: Optional[int],
    ) -> tuple[str, Optional[str], list[RankedRecipe]]:
        """One retrieve→rank→fallback pass. diet and exclude_allergens always
        come from the request (never relaxed — they're safety constraints)."""
        if mode == "hybrid":
            candidates = fetch_hybrid(
                session, resolved.ingredient_ids, query_vec,
                diet=req.diet, exclude_allergens=req.exclude_allergens,
                max_time=max_time, cuisines=cuisines, meal_type=meal_type,
                nutrition_goals=nutrition_goals, limit=CANDIDATE_POOL,
            )
            # Disliked ingredients aren't hard-filtered (soft preference); demote
            # them in ranking so they sink but remain if nothing clean fits.
            disliked = disliked_recipe_ids(
                session, [c.id for c in candidates], req.disliked_ingredients
            )
            # Rank the full pool; apply_fallback trims to req.limit (it may need
            # the wider pool to find swap-eligible recipes).
            pool = annotate(candidates, limit=CANDIDATE_POOL, disliked_ids=disliked)
        else:
            candidates = fetch_candidates(
                session, resolved.ingredient_ids,
                diet=req.diet, exclude_allergens=req.exclude_allergens,
                max_time=max_time, cuisines=cuisines, meal_type=meal_type,
                nutrition_goals=nutrition_goals, limit=CANDIDATE_POOL,
            )
            disliked = disliked_recipe_ids(
                session, [c.id for c in candidates], req.disliked_ingredients
            )
            pool = rank(candidates, limit=CANDIDATE_POOL, disliked_ids=disliked)
        return apply_fallback(
            session, pool, resolved.ingredient_ids, limit=req.limit, disliked_ids=disliked
        )

    fb_mode, explanation, results = run(
        nutrition_goals=req.nutrition_goals, cuisines=req.cuisines,
        meal_type=req.meal_type, max_time=req.max_time_minutes,
    )

    # Graceful degradation: if the soft filters emptied the list, retry with them
    # set aside (nutrition goals first, then cuisine/meal/time) so the user still
    # sees the closest matches — flagged so they know these may not fit the goals.
    if not results:
        has_other = bool(req.cuisines) or req.meal_type is not None or req.max_time_minutes is not None
        if req.nutrition_goals:
            m, _e, res = run(
                nutrition_goals=[], cuisines=req.cuisines,
                meal_type=req.meal_type, max_time=req.max_time_minutes,
            )
            if res:
                fb_mode, explanation, results = "relaxed", _relaxed_explanation(req.nutrition_goals, False), res
        if not results and (req.nutrition_goals or has_other):
            m, _e, res = run(nutrition_goals=[], cuisines=[], meal_type=None, max_time=None)
            if res:
                fb_mode, explanation, results = (
                    "relaxed",
                    _relaxed_explanation(req.nutrition_goals, has_other),
                    res,
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
