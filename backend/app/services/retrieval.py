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

# Lives in derivation.py because that is the single write path and the importers
# and estimators need the same predicate; re-exported here so the long-standing
# retrieval.nutrition_usable call sites keep resolving.
from app.services.derivation import nutrition_usable, plausible_bounds  # noqa: F401

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
        source=recipe.source,
        nutrition_estimated=recipe.nutrition_estimated,
        nutrition_source=recipe.nutrition_source,
        matched_weight=round(matched_w, 4),
        missing_weight=round(missing_w, 4),
        matched_essential_weight=round(matched_ess_w, 4),
        total_essential_weight=round(total_ess_w, 4),
        missing_substantive=missing_substantive,
    )


def _nutrition_order(goals: Iterable[str]) -> list:
    """SQL ordering that serves the requested goals best-first.

    Needed in browse mode: with no pantry to rank against, an arbitrary slice of
    compliant recipes would hand ranking a pool that may exclude the corpus's
    genuinely highest-protein recipes entirely.

    Clamped at NUTRI_FIT_CAP multiples of each threshold, mirroring nutrition_fit.
    This sort SELECTS the candidate pool, so an unclamped ORDER BY made the pool
    the corpus's most mis-parsed rows and ranking never saw a correct recipe to
    promote. Clamping ties everything past the cap and lets Recipe.id settle it.
    """
    macro = {
        "high_protein": (Recipe.nutrition["protein_g"].astext.cast(Float),
                         settings.NUTRI_HIGH_PROTEIN_G, False),
        "low_calorie": (Recipe.nutrition["calories"].astext.cast(Float),
                        settings.NUTRI_LOW_CALORIE_KCAL, True),
        "low_fat": (Recipe.nutrition["fat_g"].astext.cast(Float),
                    settings.NUTRI_LOW_FAT_G, True),
        "low_carb": (Recipe.nutrition["carbs_g"].astext.cast(Float),
                     settings.NUTRI_LOW_CARB_G, True),
    }
    order = []
    for goal in goals:
        if goal in macro:
            col, threshold, ascending = macro[goal]
            # least() for both directions: past the cap a row is either no better
            # (protein) or uniformly bad (calories), and in each case should tie
            # rather than dominate the ordering.
            capped = func.least(col, settings.NUTRI_FIT_CAP * threshold)
            order.append(capped.asc() if ascending else capped.desc())
    return order


def _filtered_recipe_ids(
    session: Session,
    limit: int,
    clauses: Iterable[ColumnElement] = (),
    order_by: Iterable = (),
) -> list[int]:
    """Compliant recipe ids with no pantry to rank against (browse mode)."""
    return list(
        session.execute(
            select(Recipe.id)
            .where(*clauses)
            .order_by(*order_by, Recipe.id)  # id last, purely for determinism
            .limit(limit)
        ).scalars()
    )


def _pantry_ranked_recipe_ids(
    session: Session,
    pantry_set: set[int],
    limit: int,
    clauses: Iterable[ColumnElement] = (),
    browse_order: Iterable = (),
    browse: bool = False,
) -> list[int]:
    """Recipe ids with >=1 pantry-ingredient match, ranked by match quality.

    Aggregates over recipe_ingredients (indexed on ingredient_id) instead of
    loading every Recipe + its ingredients into Python -- this bounds the
    query to the match set, not the total corpus size, however large the
    corpus grows.

    `clauses` are applied before the LIMIT so truncation selects among compliant
    recipes; joining Recipe here keeps that bound intact.

    With no pantry, `browse` decides: the caller supplied no ingredients at all
    and wants filter-only results, versus supplied some that resolved to
    nothing. The latter must stay empty — returning arbitrary recipes would
    imply we matched what they typed.
    """
    if not pantry_set:
        return (
            _filtered_recipe_ids(session, limit, clauses, browse_order)
            if browse
            else []
        )
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
    goals = list(goals)
    if goals and not nutrition_usable(nutrition):
        return False
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
    meal_type: Optional[str] = None,
    nutrition_goals: Iterable[str] = (),
) -> list[ColumnElement]:
    """Preference filters. Used to build a preferred pool, never to exclude —
    the caller tops up from the unfiltered pool when these come up short."""
    clauses: list[ColumnElement] = []
    if meal_type:
        clauses.append(Recipe.meal_types.contains([meal_type]))
    nutrition_goals = list(nutrition_goals)
    if nutrition_goals:
        # Mirror nutrition_usable() in SQL: a goal can't be honoured against
        # nutrition we don't trust, so those rows are excluded here rather than
        # surfacing as spurious top matches when ordering by a macro. Built from
        # the same bounds table the Python gate uses, so adding a bound there
        # enforces it in both places.
        for key, floor, ceiling in plausible_bounds():
            macro = Recipe.nutrition[key].astext.cast(Float)
            clauses += [macro >= floor, macro <= ceiling]
        clauses.append(Recipe.nutrition["protein_g"].astext.cast(Float) > 0)
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


def nutrition_fit(nutrition: dict, goals: Iterable[str]) -> float:
    """How well a recipe serves the requested goals, beyond merely passing them.

    Passing a threshold is binary, but "high protein" means more protein is
    better, not just >= 25g. Each goal contributes its macro normalized by its
    own threshold, signed so higher is always better (protein up; calories,
    fat and carbs down), which keeps goals comparable when several are set.
    Returns 0.0 when no goals are requested, so ordering is unaffected.

    Each term is clamped to NUTRI_FIT_CAP. Unclamped, the ratio rewards outliers
    without limit, so the rows with the most badly mis-parsed measures sorted
    above every correct recipe — the ranking actively hunted for the corpus's
    worst data. Clamping ties them instead, letting pantry fit and score decide.
    """
    goals = list(goals)
    if not goals or not nutrition_usable(nutrition):
        return 0.0
    n = nutrition or {}
    # (goal, json key, threshold setting, higher_is_better)
    terms = (
        ("high_protein", "protein_g", settings.NUTRI_HIGH_PROTEIN_G, True),
        ("low_calorie", "calories", settings.NUTRI_LOW_CALORIE_KCAL, False),
        ("low_fat", "fat_g", settings.NUTRI_LOW_FAT_G, False),
        ("low_carb", "carbs_g", settings.NUTRI_LOW_CARB_G, False),
    )
    cap = settings.NUTRI_FIT_CAP
    score = 0.0
    for goal, key, threshold, higher_is_better in terms:
        if goal not in goals:
            continue
        ratio = (n.get(key, 0.0) / threshold) if threshold else 0.0
        signed = ratio if higher_is_better else -ratio
        # Clamped both ways so per-goal terms stay commensurate on multi-goal
        # requests, which is the whole point of normalizing by the threshold.
        score += max(-cap, min(cap, signed))
    return round(score, 4)


def soft_filters_matched(
    c: RecipeCandidate,
    meal_type: Optional[str] = None,
    nutrition_goals: Iterable[str] = (),
    include_nutrition: bool = True,
) -> tuple[int, int]:
    """(satisfied, requested) over the preference-tier filters.

    `include_nutrition=False` for ranking: a nutrition goal is a direction to
    optimize, not a box to tick. "High protein" should return the highest
    protein available even when nothing clears 25 g — no vegetarian Thai recipe
    in the corpus does — so nutrition is graded by `nutrition_fit` instead of
    gating here. Strict callers keep it counted, since they ask literally.
    """
    checks: list[bool] = []
    if meal_type:
        checks.append(meal_type in (c.meal_types or []))
    if include_nutrition:
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

    `strict_soft` is the (meal_type, nutrition_goals) pair to
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
    cuisines: Iterable[str] = (),
    meal_type: Optional[str] = None,
    nutrition_goals: Iterable[str] = (),
    limit: int = 10,
    soften: bool = False,
    browse: bool = False,
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
    soft = soft_clauses(meal_type, nutrition_goals)

    browse_order = _nutrition_order(nutrition_goals)
    ordered = _pantry_ranked_recipe_ids(
        session, pantry_set, SQL_MATCH_POOL, hard + soft, browse_order, browse
    )
    if soften and soft and len(ordered) < SQL_MATCH_POOL:
        seen = set(ordered)
        ordered += [
            rid
            for rid in _pantry_ranked_recipe_ids(
                session, pantry_set, SQL_MATCH_POOL, hard, browse_order, browse
            )
            if rid not in seen
        ]
    return _ordered_candidates(
        session, pantry_set, ordered,
        diet=diet, exclude_allergens=exclude, cuisines=cuisines,
        limit=limit,
        # Nothing to match against in browse mode, so requiring a match would
        # discard every candidate.
        require_match=bool(pantry_set),
        strict_soft=None if soften else (meal_type, nutrition_goals),
    )


# --------------------------------------------------------------------------- #
# Hybrid path
# --------------------------------------------------------------------------- #
def _sql_ranked_ids(
    session: Session,
    pantry_set: set[int],
    limit: int,
    clauses: Iterable[ColumnElement] = (),
    browse_order: Iterable = (),
    browse: bool = False,
) -> list[int]:
    """SQL arm: recipe ids ranked by ingredient match, filtered before LIMIT."""
    return _pantry_ranked_recipe_ids(
        session, pantry_set, limit, clauses, browse_order, browse
    )


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
    cuisines: Iterable[str] = (),
    meal_type: Optional[str] = None,
    nutrition_goals: Iterable[str] = (),
    limit: int = 10,
    soften: bool = False,
    browse: bool = False,
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
    soft = soft_clauses(meal_type, nutrition_goals)

    browse_order = _nutrition_order(nutrition_goals)

    def _fuse(clauses: list[ColumnElement]) -> list[int]:
        sql_ids = _sql_ranked_ids(
            session, pantry_set, RRF_POOL, clauses, browse_order, browse
        )
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
        strict_soft=None if soften else (meal_type, nutrition_goals),
    )
