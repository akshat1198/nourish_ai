"""Deterministic SQL retrieval (RETR-01).

Candidate recipes are found by matching canonical pantry ingredient ids
against the recipe_ingredients join table — never against the JSONB display
copy. Hard constraints (diet / allergen / time) are applied as SQL filters.
Returns raw match stats; ranking (step 1.3) is layered on top.
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Ingredient, Recipe
from app.schemas.recommend import RecipeCandidate


def fetch_candidates(
    session: Session,
    pantry_ids: Iterable[int],
    *,
    diet: Optional[str] = None,
    exclude_allergens: Iterable[str] = (),
    max_time: Optional[int] = None,
    limit: int = 10,
) -> list[RecipeCandidate]:
    """Return recipes sharing >=1 ingredient with the pantry, post hard filters.

    Ordering here is a neutral default (most essential matches, then fewest
    missing) purely so `limit` is meaningful — the weighted score arrives in
    step 1.3.
    """
    pantry_set = set(pantry_ids)
    exclude = [a for a in exclude_allergens if a]

    query = select(Recipe).options(selectinload(Recipe.recipe_ingredients))
    if diet:
        query = query.where(Recipe.diet_labels.contains([diet]))
    if exclude:
        query = query.where(~Recipe.allergens.overlap(exclude))
    if max_time is not None:
        query = query.where(Recipe.time_minutes <= max_time)

    recipes = session.execute(query).scalars().all()
    id_to_name = {
        ing.id: ing.name for ing in session.execute(select(Ingredient)).scalars()
    }

    candidates: list[RecipeCandidate] = []
    for recipe in recipes:
        matched: list[str] = []
        missing: list[str] = []
        matched_essential = 0
        total_essential = 0
        for ri in recipe.recipe_ingredients:
            if ri.essential:
                total_essential += 1
            name = id_to_name.get(ri.ingredient_id, "unknown")
            if ri.ingredient_id in pantry_set:
                matched.append(name)
                if ri.essential:
                    matched_essential += 1
            else:
                missing.append(name)

        if not matched:
            continue

        candidates.append(
            RecipeCandidate(
                id=recipe.id,
                title=recipe.title,
                time_minutes=recipe.time_minutes,
                diet_labels=recipe.diet_labels,
                allergens=recipe.allergens,
                tags=recipe.tags,
                nutrition=recipe.nutrition,
                matched_ingredients=matched,
                missing_ingredients=missing,
                matched_essential=matched_essential,
                total_essential=total_essential,
            )
        )

    candidates.sort(
        key=lambda c: (c.matched_essential, -len(c.missing_ingredients)), reverse=True
    )
    return candidates[:limit]
