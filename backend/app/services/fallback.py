"""Low-confidence fallback.

When the best recipe barely uses the pantry, an empty-ish list is a bad answer.
Instead we switch modes:

  substitution_first — some recipes become reachable by swapping in something the
      user already has (mechanical lookup in the substitutions table — no LLM).
  shopping_assisted  — nothing matches well; surface the closest recipes plus what
      to buy (each recipe already carries its missing_ingredients).

Confidence is the top recipe's essential-ingredient coverage; below
FALLBACK_COVERAGE_THRESHOLD we fall back.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import Ingredient, Recipe, Substitution
from app.schemas.recommend import RankedRecipe, SubstitutionSuggestion
from app.services.ranking import order_key


def _coverage(r: RankedRecipe) -> float:
    return r.matched_essential / r.total_essential if r.total_essential else 0.0


def substitution_suggestions(
    session: Session, recipe_ids: Iterable[int], pantry_ids: Iterable[int]
) -> dict[int, list[SubstitutionSuggestion]]:
    """For each recipe, essential ingredients it lacks that a pantry item can replace.

    A substitutions row (ingredient_id -> substitute_id) means `ingredient` may be
    replaced by `substitute`. So a missing essential X is coverable when the pantry
    holds some Y with a row (ingredient_id=X, substitute_id=Y).
    """
    pantry = set(pantry_ids)
    ids = list(recipe_ids)
    if not ids or not pantry:
        return {}

    id_to_name = {i.id: i.name for i in session.execute(select(Ingredient)).scalars()}
    # missing_ingredient_id -> {substitute_id: ratio}
    subs: dict[int, dict[int, str]] = defaultdict(dict)
    for s in session.execute(select(Substitution)).scalars():
        subs[s.ingredient_id][s.substitute_id] = s.ratio

    recipes = session.execute(
        select(Recipe)
        .where(Recipe.id.in_(ids))
        .options(selectinload(Recipe.recipe_ingredients))
    ).scalars()

    out: dict[int, list[SubstitutionSuggestion]] = {}
    for recipe in recipes:
        suggestions: list[SubstitutionSuggestion] = []
        for ri in recipe.recipe_ingredients:
            if not ri.essential or ri.ingredient_id in pantry:
                continue
            for sub_id, ratio in subs.get(ri.ingredient_id, {}).items():
                if sub_id in pantry:
                    suggestions.append(
                        SubstitutionSuggestion(
                            missing=id_to_name.get(ri.ingredient_id, "?"),
                            use=id_to_name.get(sub_id, "?"),
                            ratio=ratio,
                        )
                    )
                    break
        if suggestions:
            out[recipe.id] = suggestions
    return out


def apply_fallback(
    session: Session,
    ranked: list[RankedRecipe],
    pantry_ids: Iterable[int],
    *,
    limit: int = 50,
    disliked_ids: Optional[set[int]] = None,
) -> tuple[str, Optional[str], list[RankedRecipe]]:
    """Classify confidence and return (mode, explanation, results[:limit]).

    `ranked` should be the WIDE candidate pool (not pre-trimmed to `limit`), so
    the substitution search can reach low-coverage-but-swappable recipes that
    fall outside the top-`limit`. `disliked_ids` keeps the soft dislike demotion
    intact through the substitution_first re-sort (a disliked recipe shouldn't
    jump the queue just because it's swap-enabled).
    """
    disliked_ids = disliked_ids or set()
    threshold = settings.FALLBACK_COVERAGE_THRESHOLD
    top_cov = _coverage(ranked[0]) if ranked else 0.0
    if ranked and top_cov >= threshold:
        return "normal", None, ranked[:limit]

    # Try substitution_first over the FULL pool: attach swaps the pantry enables.
    sugg = substitution_suggestions(session, [r.id for r in ranked], pantry_ids)
    if sugg:
        enriched = [r.model_copy(update={"substitutions": sugg.get(r.id, [])}) for r in ranked]
        # Reuse the ranking tiers rather than restate them: being swap-enabled is
        # only a tie-break BELOW what the user actually asked for. Sorting on
        # swaps first is what let a low-protein recipe head a high-protein
        # request — this mode fires often, so its ordering has to match rank()'s.
        enriched.sort(
            key=lambda r: (*order_key(r, disliked_ids), len(r.substitutions), r.score),
            reverse=True,
        )
        n = sum(1 for r in enriched if r.substitutions)
        return (
            "substitution_first",
            f"Nothing matched your pantry closely, but {n} recipe(s) work if you "
            "substitute an ingredient you already have.",
            enriched[:limit],
        )

    return (
        "shopping_assisted",
        "We couldn't match much of your pantry. Here are the closest recipes and "
        "what you'd need to buy (see each recipe's missing_ingredients).",
        ranked[:limit],
    )
