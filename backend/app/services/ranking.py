"""Recipe ranking (RETR-03).

Turns raw match stats from retrieval into a scored, explained ordering.

    score = W_COVERAGE * coverage
          - W_MISSING  * missing_norm
          + W_TIME     * time_fit

where
    coverage     = matched_essential / total_essential   (1.0 if no essentials)
    missing_norm = missing_count / (missing_count + matched_count)
    time_fit     = clamp(1 - time_minutes / TIME_REFERENCE, 0, 1)

Weights live in config so they are tunable without code changes; bump
RANKING_VERSION when they change (invalidates the recommendation cache).
"""
from __future__ import annotations

from app.core.config import settings
from app.schemas.recommend import RankedRecipe, RecipeCandidate


def _score(candidate: RecipeCandidate, disliked_ids: set[int] | None = None) -> float:
    coverage = (
        candidate.matched_essential / candidate.total_essential
        if candidate.total_essential
        else 1.0
    )
    matched_n = len(candidate.matched_ingredients)
    missing_n = len(candidate.missing_ingredients)
    denom = matched_n + missing_n
    missing_norm = missing_n / denom if denom else 0.0
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
    return score


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


def _to_ranked(c: RecipeCandidate, disliked_ids: set[int] | None = None) -> RankedRecipe:
    why = _why(c)
    if disliked_ids and c.id in disliked_ids:
        why += "; deprioritized (contains an ingredient you dislike)"
    return RankedRecipe(**c.model_dump(), score=round(_score(c, disliked_ids), 4), why=why)


def rank(
    candidates: list[RecipeCandidate],
    *,
    limit: int,
    disliked_ids: set[int] | None = None,
) -> list[RankedRecipe]:
    """Score, then re-order by score (SQL path).

    `disliked_ids` (recipe ids containing a disliked ingredient) get a soft
    penalty so they sink to the bottom but remain — picked only if nothing clean
    fits. Omitted => behaviour is identical to before.
    """
    ranked = [_to_ranked(c, disliked_ids) for c in candidates]
    ranked.sort(key=lambda r: r.score, reverse=True)
    return ranked[:limit]


def annotate(
    candidates: list[RecipeCandidate],
    *,
    limit: int,
    disliked_ids: set[int] | None = None,
) -> list[RankedRecipe]:
    """Score + explain but PRESERVE incoming order (hybrid path keeps RRF order).

    `score` is the ingredient-fit score for display/explanation; ordering is the
    caller's (fusion) relevance order, not re-sorted by score. When `disliked_ids`
    is given, disliked recipes are stably moved to the bottom (RRF order preserved
    within the clean group and within the disliked group) — the fusion-order
    analogue of rank()'s score penalty.
    """
    ranked = [_to_ranked(c, disliked_ids) for c in candidates[:limit]]
    if disliked_ids:
        ranked.sort(key=lambda r: r.id in disliked_ids)  # stable: disliked sink last
    return ranked
