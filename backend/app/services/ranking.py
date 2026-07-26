"""Recipe ranking.

Turns raw match stats from retrieval into a scored, explained ordering.

    score = W_COVERAGE * coverage
          - W_MISSING  * missing_norm
          + W_TIME     * time_fit

where
    coverage     = matched_essential_weight / total_essential_weight  (1.0 if none)
    missing_norm = missing_weight / (missing_weight + matched_weight)
    time_fit     = clamp(1 - time_minutes / TIME_REFERENCE, 0, 1)

Ingredients are weighted by category (see RANK_CAT_WEIGHTS): a matched chicken
counts for far more than a matched cumin. Counting them equally made spice-dense
cuisines win on any stocked spice rack, regardless of the protein or vegetable.
Candidates without weighted stats fall back to raw counts.

Ordering is strict/lexicographic rather than a score blend — see `rank`. Weights
live in config so they are tunable without code changes; bump RANKING_VERSION
when they change (invalidates the recommendation cache).
"""
from __future__ import annotations

from typing import NamedTuple

from app.core.config import settings
from app.core.cuisines import cuisine_matches
from app.schemas.recommend import RankedRecipe, RecipeCandidate


def _weights(candidate: RecipeCandidate) -> tuple[float, float, float, float]:
    """(matched, missing, matched_essential, total_essential) as weights.

    Falls back to raw counts when retrieval did not supply weighted stats, so a
    hand-built candidate still scores sensibly.
    """
    matched = (
        candidate.matched_weight
        if candidate.matched_weight is not None
        else float(len(candidate.matched_ingredients))
    )
    missing = (
        candidate.missing_weight
        if candidate.missing_weight is not None
        else float(len(candidate.missing_ingredients))
    )
    matched_ess = (
        candidate.matched_essential_weight
        if candidate.matched_essential_weight is not None
        else float(candidate.matched_essential)
    )
    total_ess = (
        candidate.total_essential_weight
        if candidate.total_essential_weight is not None
        else float(candidate.total_essential)
    )
    return matched, missing, matched_ess, total_ess


def _score(
    candidate: RecipeCandidate,
    disliked_ids: set[int] | None = None,
    taste_scores: dict[int, float] | None = None,
) -> float:
    matched_w, missing_w, matched_ess_w, total_ess_w = _weights(candidate)
    coverage = matched_ess_w / total_ess_w if total_ess_w else 1.0
    denom = matched_w + missing_w
    missing_norm = missing_w / denom if denom else 0.0
    time_fit = 1 - candidate.time_minutes / settings.RANK_TIME_REFERENCE
    time_fit = max(0.0, min(1.0, time_fit))

    score = (
        settings.RANK_W_COVERAGE * coverage
        - settings.RANK_W_MISSING * missing_norm
        + settings.RANK_W_TIME * time_fit
    )
    # Soft demotion: sink disliked recipes beneath clean ones without removing them.
    if disliked_ids and candidate.id in disliked_ids:
        score -= settings.RANK_W_DISLIKE
    # Personalization: applied here, on an already hard-filtered
    # candidate — this can only reorder the safe set, never surface a
    # diet/allergen violation. Small weight; 0.0 contribution if no signal.
    if taste_scores:
        score += settings.RANK_W_TASTE * taste_scores.get(candidate.id, 0.0)
    return score


class SoftFilters(NamedTuple):
    """The request's preference-tier filters, plus the near-hard cuisine tier.

    Bundled so ranking can report what each recipe satisfies without every
    caller threading six parameters through.
    """

    max_time: int | None = None
    meal_type: str | None = None
    nutrition_goals: tuple[str, ...] = ()
    cuisines: tuple[str, ...] = ()

    @classmethod
    def from_request(cls, req) -> "SoftFilters":
        return cls(
            max_time=req.max_time_minutes,
            meal_type=req.meal_type,
            nutrition_goals=tuple(req.nutrition_goals),
            cuisines=tuple(req.cuisines),
        )


def _why(candidate: RecipeCandidate) -> str:
    parts = []
    if candidate.total_essential:
        parts.append(
            f"uses {candidate.matched_essential}/{candidate.total_essential} "
            "key ingredients"
        )
    else:
        parts.append(f"uses {len(candidate.matched_ingredients)} of your ingredients")
    missing = candidate.missing_ingredients
    if not missing:
        parts.append("nothing missing")
    elif len(missing) <= 3:
        parts.append("missing only " + ", ".join(missing))
    else:
        parts.append(f"missing {len(missing)} items")
    parts.append(f"ready in {candidate.time_minutes} min")
    return "; ".join(parts)


def _to_ranked(
    c: RecipeCandidate,
    disliked_ids: set[int] | None = None,
    taste_scores: dict[int, float] | None = None,
    filters: SoftFilters | None = None,
) -> RankedRecipe:
    from app.services.retrieval import nutrition_fit, soft_filters_matched

    why = _why(c)
    if disliked_ids and c.id in disliked_ids:
        why += "; deprioritized (contains an ingredient you dislike)"
    # Only claim a personalization match when the term is materially positive —
    # keeps the explanation honest rather than firing on noise near zero.
    if taste_scores and taste_scores.get(c.id, 0.0) > 0.15:
        why += "; matches recipes you've saved"
    score = round(_score(c, disliked_ids, taste_scores), 4)

    f = filters or SoftFilters()
    # Nutrition is deliberately excluded from the binary count — it ranks by
    # degree via nutrition_fit, so a goal nothing can satisfy still orders the
    # results best-first instead of flattening them all to "matched 0".
    matched, requested = soft_filters_matched(
        c, f.max_time, f.meal_type, f.nutrition_goals, include_nutrition=False
    )
    in_cuisine = (
        cuisine_matches(c.cuisine, c.region, list(f.cuisines)) if f.cuisines else True
    )
    if not in_cuisine:
        why += "; not in the cuisine you picked"
    return RankedRecipe(
        **c.model_dump(),
        score=score,
        why=why,
        filters_matched=matched,
        filters_requested=requested,
        cuisine_matched=in_cuisine,
        pantry_complete=c.missing_substantive == 0,
        nutrition_fit=nutrition_fit(c.nutrition, f.nutrition_goals),
    )


def order_key(r: RankedRecipe, disliked_ids: set[int] | None = None) -> tuple:
    """Strict, lexicographic — not a score blend.

    What the user asked for beats what their pantry happens to hold: the
    filters rank above pantry completeness, so asking for high-protein can
    never put a low-protein recipe on top just because nothing is missing
    from it. Cuisine outranks everything below it, and a disliked recipe still
    sinks beneath every clean one.

    `nutrition_fit` grades within the passing set (more protein, fewer carbs)
    and is 0.0 for every recipe when no nutrition goal is set, so it changes
    nothing on requests that don't ask for one.
    """
    return (
        r.cuisine_matched,
        not (disliked_ids and r.id in disliked_ids),
        r.filters_matched,
        r.nutrition_fit,
        r.pantry_complete,
    )


def rank(
    candidates: list[RecipeCandidate],
    *,
    limit: int,
    disliked_ids: set[int] | None = None,
    taste_scores: dict[int, float] | None = None,
    filters: SoftFilters | None = None,
) -> list[RankedRecipe]:
    """Score, then order strictly (SQL path).

    Tie-break within an equal tier is the weighted-fit score. `disliked_ids`
    (recipe ids containing a disliked ingredient) sink to the bottom but remain
    — picked only if nothing clean fits. `taste_scores` adds a small
    personalization term, applied to already-filtered candidates so it can only
    reorder the safe set.
    """
    ranked = [_to_ranked(c, disliked_ids, taste_scores, filters) for c in candidates]
    ranked.sort(key=lambda r: (*order_key(r, disliked_ids), r.score), reverse=True)
    return ranked[:limit]


def annotate(
    candidates: list[RecipeCandidate],
    *,
    limit: int,
    disliked_ids: set[int] | None = None,
    taste_scores: dict[int, float] | None = None,
    filters: SoftFilters | None = None,
) -> list[RankedRecipe]:
    """Score + order strictly, with fusion order as the final tie-break (hybrid).

    Same lexicographic tiers as `rank`, but where that falls back to the score,
    this keeps the caller's RRF relevance order — a stable sort leaves recipes
    in the same tier exactly as fusion ranked them.
    """
    ranked = [
        _to_ranked(c, disliked_ids, taste_scores, filters) for c in candidates[:limit]
    ]
    ranked.sort(key=lambda r: order_key(r, disliked_ids), reverse=True)
    return ranked
