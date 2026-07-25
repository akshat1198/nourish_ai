"""Retrieval: deterministic SQL and hybrid SQL+vector.

Matching always runs against the recipe_ingredients join table, never the
JSONB display copy. The hybrid path fuses an ingredient-match ranking with a
vector-similarity ranking using Reciprocal Rank Fusion.

Hard constraints are applied INSIDE each arm, before its LIMIT, so the pool is
drawn from compliant recipes only — filtering after truncation discarded
compliant recipes before the filters were ever consulted (a vegan+italian
request had 45 eligible recipes and surfaced none). `_passes_filters` still runs
post-fusion as a defense-in-depth assertion, so a non-compliant recipe cannot
leak in even if an arm's SQL is wrong.
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import ColumnElement, Float, and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import category_weight, settings
from app.core.cuisines import cuisine_matches, parse_cuisine_id
from app.models import Ingredient, Recipe, RecipeIngredient
from app.schemas.recommend import RecipeCandidate

RRF_K = 60  # RRF damping constant; larger => flatter rank contribution
# Safe at this size because each arm is already filtered when it truncates; the
# pool is compliant candidates, and memory stays bounded by the SQL LIMIT.
RRF_POOL = 120  # top-N taken from each arm before fusion
SQL_MATCH_POOL = 200  # top-N pantry-matched recipe ids considered


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _ingredient_index(session: Session) -> dict[int, tuple[str, str]]:
    """ingredient_id -> (name, category). One query, reused per request."""
    return {
        ing.id: (ing.name, ing.category)
        for ing in session.execute(select(Ingredient)).scalars()
    }


def _build_candidate(
    recipe: Recipe, pantry_set: set[int], index: dict[int, tuple[str, str]]
) -> RecipeCandidate:
    matched: list[str] = []
    missing: list[str] = []
    matched_essential = 0
    total_essential = 0
    matched_w = 0.0
    missing_w = 0.0
    matched_ess_w = 0.0
    total_ess_w = 0.0
    missing_substantive = 0
    for ri in recipe.recipe_ingredients:
        name, category = index.get(ri.ingredient_id, ("unknown", ""))
        weight = category_weight(category)
        if ri.essential:
            total_essential += 1
            total_ess_w += weight
        if ri.ingredient_id in pantry_set:
            matched.append(name)
            matched_w += weight
            if ri.essential:
                matched_essential += 1
                matched_ess_w += weight
        else:
            missing.append(name)
            missing_w += weight
            if weight >= settings.RANK_SUBSTANTIVE_MIN_WEIGHT:
                missing_substantive += 1
    return RecipeCandidate(
        id=recipe.id,
        title=recipe.title,
        time_minutes=recipe.time_minutes,
        diet_labels=recipe.diet_labels,
        allergens=recipe.allergens,
        tags=recipe.tags,
        cuisine=recipe.cuisine,
        region=recipe.region,
        meal_types=recipe.meal_types or [],
        nutrition=recipe.nutrition,
        matched_ingredients=matched,
        missing_ingredients=missing,
        matched_essential=matched_essential,
        total_essential=total_essential,
        matched_weight=round(matched_w, 4),
        missing_weight=round(missing_w, 4),
        matched_essential_weight=round(matched_ess_w, 4),
        total_essential_weight=round(total_ess_w, 4),
        missing_substantive=missing_substantive,
    )


def _pantry_ranked_recipe_ids(
    session: Session,
    pantry_set: set[int],
    limit: int,
    clauses: Iterable[ColumnElement] = (),
) -> list[int]:
    """Recipe ids with >=1 pantry-ingredient match, ranked by match quality.

    Aggregates over recipe_ingredients (indexed on ingredient_id) instead of
    loading every Recipe + its ingredients into Python -- this bounds the
    query to the match set, not the total corpus size, however large the
    corpus grows.

    `clauses` are applied before the LIMIT so truncation selects among compliant
    recipes; joining Recipe here keeps that bound intact.
    """
    if not pantry_set:
        return []
    pantry_list = list(pantry_set)
    matched_total = func.count().filter(RecipeIngredient.ingredient_id.in_(pantry_list))
    matched_essential = func.count().filter(
        RecipeIngredient.ingredient_id.in_(pantry_list),
        RecipeIngredient.essential.is_(True),
    )
    missing = func.count() - matched_total
    query = select(RecipeIngredient.recipe_id)
    clauses = list(clauses)
    if clauses:
        query = query.join(Recipe, Recipe.id == RecipeIngredient.recipe_id).where(*clauses)
    query = (
        query.group_by(RecipeIngredient.recipe_id)
        .having(matched_total > 0)
        .order_by(matched_essential.desc(), missing.asc())
        .limit(limit)
    )
    return list(session.execute(query).scalars())


def _nutrition_ok(nutrition: dict, goals: Iterable[str]) -> bool:
    """AND semantics: the recipe must meet every requested per-serving goal."""
    n = nutrition or {}
    for g in goals:
        if g == "high_protein" and n.get("protein_g", 0) < settings.NUTRI_HIGH_PROTEIN_G:
            return False
        if g == "low_calorie" and n.get("calories", float("inf")) > settings.NUTRI_LOW_CALORIE_KCAL:
            return False
        if g == "low_fat" and n.get("fat_g", float("inf")) > settings.NUTRI_LOW_FAT_G:
            return False
        if g == "low_carb" and n.get("carbs_g", float("inf")) > settings.NUTRI_LOW_CARB_G:
            return False
    return True


def _cuisine_clause(cuisines: Iterable[str]) -> Optional[ColumnElement]:
    """OR across cuisine ids; a top-level id matches every region under it."""
    ids = [c for c in cuisines if c]
    if not ids:
        return None
    terms = []
    for cid in ids:
        top, region = parse_cuisine_id(cid)
        terms.append(
            and_(Recipe.cuisine == top, Recipe.region == region)
            if region
            else Recipe.cuisine == top
        )
    return or_(*terms)


def hard_clauses(
    diet: Optional[str],
    exclude_allergens: Iterable[str],
    cuisines: Iterable[str] = (),
) -> list[ColumnElement]:
    """Filters a result may never violate: diet, allergens, and cuisine.

    Diet and allergens are safety constraints. Cuisine sits just below them —
    it is never silently substituted, so it is enforced here rather than being
    left to ranking; a shortfall is handled by the caller, not by quietly
    serving another cuisine.
    """
    clauses: list[ColumnElement] = []
    if diet:
        clauses.append(Recipe.diet_labels.contains([diet]))
    exclude = [a for a in exclude_allergens if a]
    if exclude:
        clauses.append(~Recipe.allergens.overlap(exclude))
    cuisine = _cuisine_clause(cuisines)
    if cuisine is not None:
        clauses.append(cuisine)
    return clauses


def soft_clauses(
    max_time: Optional[int] = None,
    meal_type: Optional[str] = None,
    nutrition_goals: Iterable[str] = (),
) -> list[ColumnElement]:
    """Preference filters. Used to build a preferred pool, never to exclude —
    the caller tops up from the unfiltered pool when these come up short."""
    clauses: list[ColumnElement] = []
    if max_time is not None:
        clauses.append(Recipe.time_minutes <= max_time)
    if meal_type:
        clauses.append(Recipe.meal_types.contains([meal_type]))
    for goal in nutrition_goals:
        # Missing nutrition yields NULL and drops the row, matching
        # _nutrition_ok's treatment of an absent macro as a failed goal.
        if goal == "high_protein":
            clauses.append(
                Recipe.nutrition["protein_g"].astext.cast(Float)
                >= settings.NUTRI_HIGH_PROTEIN_G
            )
        elif goal == "low_calorie":
            clauses.append(
                Recipe.nutrition["calories"].astext.cast(Float)
                <= settings.NUTRI_LOW_CALORIE_KCAL
            )
        elif goal == "low_fat":
            clauses.append(
                Recipe.nutrition["fat_g"].astext.cast(Float) <= settings.NUTRI_LOW_FAT_G
            )
        elif goal == "low_carb":
            clauses.append(
                Recipe.nutrition["carbs_g"].astext.cast(Float)
                <= settings.NUTRI_LOW_CARB_G
            )
    return clauses


def soft_filters_matched(
    c: RecipeCandidate,
    max_time: Optional[int] = None,
    meal_type: Optional[str] = None,
    nutrition_goals: Iterable[str] = (),
) -> tuple[int, int]:
    """(satisfied, requested) over the preference-tier filters."""
    checks: list[bool] = []
    if max_time is not None:
        checks.append(c.time_minutes <= max_time)
    if meal_type:
        checks.append(meal_type in (c.meal_types or []))
    for goal in nutrition_goals:
        checks.append(_nutrition_ok(c.nutrition, [goal]))
    return sum(checks), len(checks)


def _passes_filters(
    c: RecipeCandidate,
    diet: Optional[str],
    exclude_allergens: Iterable[str],
    cuisines: Iterable[str] = (),
) -> bool:
    """Post-fusion assertion over the hard tier only.

    The arms already applied these in SQL; re-checking here means a bug in an
    arm's query still cannot leak a diet/allergen violation into results. Soft
    filters are deliberately absent — top-up candidates are allowed to miss them
    and are demoted by ranking instead.
    """
    if diet and diet not in c.diet_labels:
        return False
    if set(exclude_allergens) & set(c.allergens):
        return False
    cuisines = list(cuisines)
    if cuisines and not cuisine_matches(c.cuisine, c.region, cuisines):
        return False
    return True


# --------------------------------------------------------------------------- #
# SQL path
# --------------------------------------------------------------------------- #
def _ordered_candidates(
    session: Session,
    pantry_set: set[int],
    ordered_ids: list[int],
    *,
    diet: Optional[str],
    exclude_allergens: Iterable[str],
    cuisines: Iterable[str],
    limit: int,
    require_match: bool,
    strict_soft: Optional[tuple] = None,
) -> list[RecipeCandidate]:
    """Hydrate ids into candidates, preserving `ordered_ids` order.

    `strict_soft` is the (max_time, meal_type, nutrition_goals) triple to
    re-assert when the caller did NOT ask for softening — the same
    defense-in-depth as `_passes_filters`, so a bug in an arm's SQL can't leak a
    filter violation to a caller that expects exact semantics.
    """
    if not ordered_ids:
        return []
    index = _ingredient_index(session)
    recipes = {
        r.id: r
        for r in session.execute(
            select(Recipe)
            .where(Recipe.id.in_(ordered_ids))
            .options(selectinload(Recipe.recipe_ingredients))
        ).scalars()
    }
    out: list[RecipeCandidate] = []
    for rid in ordered_ids:
        recipe = recipes.get(rid)
        if recipe is None:
            continue
        c = _build_candidate(recipe, pantry_set, index)
        if require_match and not c.matched_ingredients:
            continue
        if not _passes_filters(c, diet, exclude_allergens, cuisines):
            continue
        if strict_soft is not None:
            matched, requested = soft_filters_matched(c, *strict_soft)
            if matched != requested:
                continue
        out.append(c)
        if len(out) >= limit:
            break
    return out


def fetch_candidates(
    session: Session,
    pantry_ids: Iterable[int],
    *,
    diet: Optional[str] = None,
    exclude_allergens: Iterable[str] = (),
    max_time: Optional[int] = None,
    cuisines: Iterable[str] = (),
    meal_type: Optional[str] = None,
    nutrition_goals: Iterable[str] = (),
    limit: int = 10,
    soften: bool = False,
) -> list[RecipeCandidate]:
    """Recipes sharing >=1 ingredient with the pantry, filters enforced.

    Every filter is strict by default: "under 20 minutes" returns recipes under
    20 minutes, which the agent tools, MCP surface, and eval harness rely on.
    `soften=True` demotes the preference tier instead of excluding it — after
    the strict matches, recipes that miss time/meal-type/nutrition are appended
    so a narrow preference can't empty the list. Only /v1/recommendations opts
    in, because only it has a ranking layer to sort the two groups.
    """
    pantry_set = set(pantry_ids)
    exclude = [a for a in exclude_allergens if a]
    hard = hard_clauses(diet, exclude, cuisines)
    soft = soft_clauses(max_time, meal_type, nutrition_goals)

    ordered = _pantry_ranked_recipe_ids(session, pantry_set, SQL_MATCH_POOL, hard + soft)
    if soften and soft and len(ordered) < SQL_MATCH_POOL:
        seen = set(ordered)
        ordered += [
            rid
            for rid in _pantry_ranked_recipe_ids(
                session, pantry_set, SQL_MATCH_POOL, hard
            )
            if rid not in seen
        ]
    return _ordered_candidates(
        session, pantry_set, ordered,
        diet=diet, exclude_allergens=exclude, cuisines=cuisines,
        limit=limit, require_match=True,
        strict_soft=None if soften else (max_time, meal_type, nutrition_goals),
    )


# --------------------------------------------------------------------------- #
# Hybrid path
# --------------------------------------------------------------------------- #
def _sql_ranked_ids(
    session: Session,
    pantry_set: set[int],
    limit: int,
    clauses: Iterable[ColumnElement] = (),
) -> list[int]:
    """SQL arm: recipe ids ranked by ingredient match, filtered before LIMIT."""
    return _pantry_ranked_recipe_ids(session, pantry_set, limit, clauses)


def _vector_ranked_ids(
    session: Session,
    query_vec: list[float],
    limit: int,
    clauses: Iterable[ColumnElement] = (),
) -> list[int]:
    """Vector arm: recipe ids by ascending cosine distance, filtered before LIMIT."""
    rows = session.execute(
        select(Recipe.id)
        .where(Recipe.embedding.isnot(None), *clauses)
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
    cuisines: Iterable[str] = (),
    meal_type: Optional[str] = None,
    nutrition_goals: Iterable[str] = (),
    limit: int = 10,
    soften: bool = False,
) -> list[RecipeCandidate]:
    """Fuse SQL match + vector similarity, both arms filtered before truncation.

    Strict by default, like `fetch_candidates`. Under `soften=True` fusion runs
    twice: once over arms restricted to the soft filters, once over arms
    carrying only the hard ones, so soft-matching recipes lead the pool and the
    rest follow — a narrow preference demotes rather than empties.
    """
    pantry_set = set(pantry_ids)
    exclude = [a for a in exclude_allergens if a]
    hard = hard_clauses(diet, exclude, cuisines)
    soft = soft_clauses(max_time, meal_type, nutrition_goals)

    def _fuse(clauses: list[ColumnElement]) -> list[int]:
        sql_ids = _sql_ranked_ids(session, pantry_set, RRF_POOL, clauses)
        vec_ids = (
            _vector_ranked_ids(session, query_vec, RRF_POOL, clauses)
            if query_vec
            else []
        )
        return rrf_fuse([sql_ids, vec_ids])

    ordered = _fuse(hard + soft)
    if soften and soft:
        seen = set(ordered)
        ordered += [rid for rid in _fuse(hard) if rid not in seen]

    return _ordered_candidates(
        session, pantry_set, ordered,
        diet=diet, exclude_allergens=exclude, cuisines=cuisines,
        limit=limit, require_match=False,
        strict_soft=None if soften else (max_time, meal_type, nutrition_goals),
    )
