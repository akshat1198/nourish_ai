"""Retrieval: deterministic SQL (RETR-01) and hybrid SQL+vector (RETR-02).

Matching always runs against the recipe_ingredients join table, never the
JSONB display copy. The hybrid path fuses an ingredient-match ranking with a
vector-similarity ranking using Reciprocal Rank Fusion, then applies the hard
constraints (diet / allergen / time) POST-fusion so a semantically-similar but
non-compliant recipe can never leak into results.
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Ingredient, Recipe
from app.schemas.recommend import RecipeCandidate

RRF_K = 60  # RRF damping constant; larger => flatter rank contribution
RRF_POOL = 30  # top-N taken from each arm before fusion


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _id_to_name(session: Session) -> dict[int, str]:
    return {ing.id: ing.name for ing in session.execute(select(Ingredient)).scalars()}


def _build_candidate(
    recipe: Recipe, pantry_set: set[int], id_to_name: dict[int, str]
) -> RecipeCandidate:
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
    return RecipeCandidate(
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


def _passes_filters(
    c: RecipeCandidate,
    diet: Optional[str],
    exclude_allergens: Iterable[str],
    max_time: Optional[int],
) -> bool:
    if diet and diet not in c.diet_labels:
        return False
    if set(exclude_allergens) & set(c.allergens):
        return False
    if max_time is not None and c.time_minutes > max_time:
        return False
    return True


# --------------------------------------------------------------------------- #
# SQL path (RETR-01)
# --------------------------------------------------------------------------- #
def fetch_candidates(
    session: Session,
    pantry_ids: Iterable[int],
    *,
    diet: Optional[str] = None,
    exclude_allergens: Iterable[str] = (),
    max_time: Optional[int] = None,
    limit: int = 10,
) -> list[RecipeCandidate]:
    """Recipes sharing >=1 ingredient with the pantry, after hard filters.

    Neutral default ordering (most essential matches, then fewest missing) so
    `limit` is meaningful; the weighted score is applied by the ranking layer.
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

    id_to_name = _id_to_name(session)
    candidates = [
        c
        for recipe in session.execute(query).scalars()
        if (c := _build_candidate(recipe, pantry_set, id_to_name)).matched_ingredients
    ]
    candidates.sort(
        key=lambda c: (c.matched_essential, -len(c.missing_ingredients)), reverse=True
    )
    return candidates[:limit]


# --------------------------------------------------------------------------- #
# Hybrid path (RETR-02)
# --------------------------------------------------------------------------- #
def _sql_ranked_ids(session: Session, pantry_set: set[int], limit: int) -> list[int]:
    """SQL arm: recipe ids ranked by ingredient match, no hard filters."""
    id_to_name = _id_to_name(session)
    query = select(Recipe).options(selectinload(Recipe.recipe_ingredients))
    scored = []
    for recipe in session.execute(query).scalars():
        c = _build_candidate(recipe, pantry_set, id_to_name)
        if c.matched_ingredients:
            scored.append((c.matched_essential, -len(c.missing_ingredients), recipe.id))
    scored.sort(reverse=True)
    return [rid for _, _, rid in scored[:limit]]


def _vector_ranked_ids(
    session: Session, query_vec: list[float], limit: int
) -> list[int]:
    """Vector arm: recipe ids by ascending cosine distance, no hard filters."""
    rows = session.execute(
        select(Recipe.id)
        .where(Recipe.embedding.isnot(None))
        .order_by(Recipe.embedding.cosine_distance(query_vec))
        .limit(limit)
    ).scalars()
    return list(rows)


def rrf_fuse(rank_lists: list[list[int]], k: int = RRF_K) -> list[int]:
    """Reciprocal Rank Fusion: score(id) = sum 1/(k + rank), rank 1-indexed."""
    scores: dict[int, float] = {}
    for ranked in rank_lists:
        for rank, rid in enumerate(ranked, start=1):
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (k + rank)
    return [rid for rid, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]


def fetch_hybrid(
    session: Session,
    pantry_ids: Iterable[int],
    query_vec: list[float],
    *,
    diet: Optional[str] = None,
    exclude_allergens: Iterable[str] = (),
    max_time: Optional[int] = None,
    limit: int = 10,
) -> list[RecipeCandidate]:
    """Fuse SQL match + vector similarity, then apply hard filters post-fusion."""
    pantry_set = set(pantry_ids)

    sql_ids = _sql_ranked_ids(session, pantry_set, RRF_POOL)
    vec_ids = _vector_ranked_ids(session, query_vec, RRF_POOL) if query_vec else []
    fused_ids = rrf_fuse([sql_ids, vec_ids])

    if not fused_ids:
        return []

    id_to_name = _id_to_name(session)
    recipes = {
        r.id: r
        for r in session.execute(
            select(Recipe)
            .where(Recipe.id.in_(fused_ids))
            .options(selectinload(Recipe.recipe_ingredients))
        ).scalars()
    }

    results: list[RecipeCandidate] = []
    for rid in fused_ids:  # preserve fused order
        recipe = recipes.get(rid)
        if recipe is None:
            continue
        c = _build_candidate(recipe, pantry_set, id_to_name)
        if _passes_filters(c, diet, exclude_allergens, max_time):
            results.append(c)
        if len(results) >= limit:
            break
    return results
