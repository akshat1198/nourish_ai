"""Recommendations endpoint — SQL and hybrid retrieval."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.auth import get_current_user_key
from app.api.deps import get_session
from app.core.config import settings
from app.core.cuisines import VALID_CUISINE_IDS, label_for
from app.schemas.recommend import RankedRecipe, RecommendRequest, RecommendResponse
from app.services.cache import get_cached, recommend_key, set_cached
from app.services.embedder import get_embedder
from app.services.experiments import assign_variant
from app.services.fallback import apply_fallback
from app.services.generation import can_generate, generate_recipes
from app.services.ingredients import disliked_recipe_ids, resolve_pantry
from app.services.pantry_text import parse_pantry_text
from app.services.personalization import taste_scores, taste_vector
from app.services.ranking import SoftFilters, annotate, rank
from app.services.retrieval import fetch_candidates, fetch_hybrid

router = APIRouter(prefix="/v1", tags=["recommendations"])

# Retrieve a wider pool than requested so ranking has room to reorder.
CANDIDATE_POOL = 50
# Below this many in-cuisine results, append other cuisines under a divider
# rather than leaving the user with almost nothing. Never blended in.
OFF_CUISINE_FLOOR = 3


def _off_cuisine_explanation(cuisines: list[str]) -> str:
    """Message for 'off_cuisine' mode. Never claims the results are what was
    asked for — they sit below a divider and carry cuisine_matched=False."""
    names = ", ".join(label_for(c) for c in cuisines)
    return (
        f"We don't have many {names} recipes that fit your pantry and filters yet. "
        "Everything below the divider is from a different cuisine."
    )


@router.post("/recommendations", response_model=RecommendResponse)
def recommend(
    req: RecommendRequest,
    response: Response,
    session: Session = Depends(get_session),
    mode: str = Query("hybrid", pattern="^(sql|hybrid)$"),
    user_key: str = Depends(get_current_user_key),
):
    bad = [c for c in req.cuisines if c not in VALID_CUISINE_IDS]
    if bad:
        raise HTTPException(422, f"unknown cuisine id(s): {', '.join(bad)}")

    # Deterministic A/B bucket from the client's persisted session
    # id. No session id (e.g. a bare API caller) -> no experiment, no gating.
    variant = (
        assign_variant(req.session_id, settings.EXPERIMENT_NAME)
        if req.session_id
        else None
    )

    # A taste vector only needs (session, user_key) — no pantry
    # resolution required — so compute it before the cache check. Personalized
    # results must not collide across users or with the shared cold-start
    # cache entry, so `user` only enters the key when this user IS personalized.
    # The "control" variant never personalizes, regardless of the
    # feature flag — that's the whole point of an A/B control arm.
    tvec = (
        taste_vector(session, user_key)
        if settings.PERSONALIZATION_ENABLED and variant != "control"
        else None
    )
    key = recommend_key(
        {
            **req.model_dump(),
            "mode": mode,
            "user": user_key if tvec is not None else None,
            "variant": variant,
        }
    )
    # Personalized responses are never cached: any feedback write (e.g.
    # dismissing a recipe) must be reflected on the very next identical
    # request, and the response cache's TTL (minutes) would otherwise silently
    # serve a pre-feedback result — the `user` key component alone only stops
    # CROSS-user collisions, not this same-user staleness. Cold-start/control
    # users are unaffected by any feedback (tscores is always {} for them), so
    # their shared cache entry stays exactly as before.
    if tvec is None:
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

    filters = SoftFilters.from_request(req)
    # No ingredients entered at all means "show me what fits my filters", which
    # must still return recipes. A pantry that was entered but resolved to
    # nothing is NOT that: it stays empty, with the names reported back in
    # unmatched_pantry, rather than implying we matched what they typed.
    browse = not (req.pantry or req.pantry_text)

    def run(*, cuisines: list[str]) -> tuple[str, Optional[str], list[RankedRecipe]]:
        """One retrieve→rank→fallback pass.

        diet and exclude_allergens always come from the request — they are
        safety constraints and are never varied. `cuisines` is the only filter
        this varies, and only to build the clearly-labelled off-cuisine group.
        Soft filters (meal type / nutrition goals) are always passed
        through: retrieval prefers them, ranking demotes what misses them.
        """
        nutrition_goals = req.nutrition_goals
        meal_type = req.meal_type
        if mode == "hybrid":
            candidates = fetch_hybrid(
                session, resolved.ingredient_ids, query_vec,
                diet=req.diet, exclude_allergens=req.exclude_allergens,
                cuisines=cuisines, meal_type=meal_type,
                nutrition_goals=nutrition_goals, limit=CANDIDATE_POOL,
                soften=True, browse=browse,
            )
            # Disliked ingredients aren't hard-filtered (soft preference); demote
            # them in ranking so they sink but remain if nothing clean fits.
            disliked = disliked_recipe_ids(
                session, [c.id for c in candidates], req.disliked_ingredients
            )
            # Personalization score per candidate. `tvec is None`
            # can mean either cold-start OR a deliberate "off" (disabled /
            # control variant) — skip the call entirely rather than pass tvec
            # through, since taste_scores(..., vec=None) treats None as "look
            # it up yourself" and would silently re-personalize a control user.
            tscores = (
                taste_scores(session, user_key, [c.id for c in candidates], tvec)
                if tvec is not None
                else {}
            )
            # Rank the full pool; apply_fallback trims to req.limit (it may need
            # the wider pool to find swap-eligible recipes).
            pool = annotate(
                candidates, limit=CANDIDATE_POOL, disliked_ids=disliked,
                taste_scores=tscores, filters=filters,
            )
        else:
            candidates = fetch_candidates(
                session, resolved.ingredient_ids,
                diet=req.diet, exclude_allergens=req.exclude_allergens,
                cuisines=cuisines, meal_type=meal_type,
                nutrition_goals=nutrition_goals, limit=CANDIDATE_POOL,
                soften=True, browse=browse,
            )
            disliked = disliked_recipe_ids(
                session, [c.id for c in candidates], req.disliked_ingredients
            )
            tscores = (
                taste_scores(session, user_key, [c.id for c in candidates], tvec)
                if tvec is not None
                else {}
            )
            pool = rank(
                candidates, limit=CANDIDATE_POOL, disliked_ids=disliked,
                taste_scores=tscores, filters=filters,
            )
        return apply_fallback(
            session, pool, resolved.ingredient_ids, limit=req.limit, disliked_ids=disliked
        )

    fb_mode, explanation, results = run(cuisines=req.cuisines)

    # A genuine shortfall is a gap in the corpus, not a reason to serve another
    # cuisine: write recipes for these exact filters, persist them, and re-run
    # so they flow through the same ranking as everything else. Fails open —
    # generate_recipes never raises, and an empty return just leaves `results`.
    generated: list[int] = []
    if len(results) < settings.GENERATION_MIN_RESULTS and can_generate(session):
        generated = generate_recipes(session, req, pantry, user_key)
        if generated:
            fb_mode, explanation, results = run(cuisines=req.cuisines)

    # Soft filters no longer empty the list — retrieval keeps near-misses in the
    # pool and ranking demotes them — so the only shortfall left to handle is
    # cuisine. It is never silently substituted: other cuisines are appended
    # below, carrying cuisine_matched=False, and can never outrank an in-cuisine
    # result because that flag is the top sort key.
    #
    # Skipped when generation just wrote recipes in this cuisine AND they came
    # back: padding then contradicts what we did, appending other cuisines and
    # announcing "we don't have many X recipes yet" immediately after producing
    # X recipes. A short, wholly in-cuisine list is the better answer — but only
    # if it isn't empty, so a generation that reported success while surfacing
    # nothing still falls through to the divider rather than showing zero.
    wrote_in_cuisine = bool(generated and results)
    if req.cuisines and not wrote_in_cuisine and len(results) < OFF_CUISINE_FLOOR:
        _m, _e, other = run(cuisines=[])
        seen = {r.id for r in results}
        extra = [r for r in other if r.id not in seen and not r.cuisine_matched]
        if extra:
            results = (results + extra)[: req.limit]
            fb_mode = "off_cuisine"
            explanation = _off_cuisine_explanation(req.cuisines)

    payload = RecommendResponse(
        results=results,
        mode=fb_mode,
        explanation=explanation,
        unmatched_pantry=resolved.unmatched,
        variant=variant,
    )
    if tvec is None:
        set_cached(key, payload.model_dump())
    response.headers["X-Cache"] = "miss" if tvec is None else "skip-personalized"
    return payload
