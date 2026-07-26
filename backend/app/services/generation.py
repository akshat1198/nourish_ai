"""Write recipes the corpus can't supply, validate them, and keep them.

The corpus is 62% Indian and has 3 Korean recipes; no amount of retrieval
fixes a cuisine that isn't there. Rather than silently serving another cuisine,
a genuine shortfall is filled by generating recipes for the exact filter
payload, then persisting them so the corpus grows toward what people actually
ask for and the next identical request is a fast DB hit.

Nothing the model says about diet or allergens is trusted. Labels are
re-derived from the generated ingredient list by `classify_and_derive`, and a
recipe whose DERIVED labels contradict the request is discarded rather than
repaired — the same fail-closed stance as `agent/validator.py`, which exists
because a model claiming "dairy-free" is the failure mode being guarded.

Fails open throughout: any error leaves the caller with whatever retrieval
found, never a 500.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.allergens import ALLERGEN_SET, clean_allergens
from app.core.config import settings
from app.core.cuisines import CUISINE_TAXONOMY, label_for, parse_cuisine_id
from app.llm.client import LLMError, get_llm, is_enabled
from app.models import GenerationEvent, Ingredient, Recipe, RecipeIngredient
from app.schemas.generation import (
    INGREDIENT_CATEGORIES,
    INGREDIENT_UNITS,
    GeneratedRecipe,
    GenerationResult,
    NewIngredient,
)
from app.schemas.recommend import RecommendRequest
from app.services.derivation import classify_and_derive, load_props, measure_to_grams
from app.services.embedder import get_embedder
from app.services.ingredients import normalize

logger = logging.getLogger(__name__)

SYSTEM = """You write real, cookable recipes that satisfy a set of constraints exactly.

Rules:
- The diet and allergen constraints are absolute. Never include an ingredient \
that violates them, and remember that vegan excludes dairy, eggs, fish, \
shellfish and honey; vegetarian excludes all meat, fish and shellfish.
- The cuisine is what the user asked for. Write food that someone from that \
cuisine would recognise, using its real techniques and ingredients.
- Prefer ingredients from the provided vocabulary, using those exact names, so \
the recipe indexes properly. Use an ingredient outside it only when the dish \
genuinely needs it, and then declare it in new_ingredients.
- Prefer the user's pantry ingredients where they fit, but do not contort the \
dish to use them and do not invent a bad recipe to avoid a shopping list.
- Never use a disliked ingredient.
- Give real quantities with units, and a method someone can actually follow.
- Every ingredient you use that is NOT in the vocabulary must appear in \
new_ingredients with accurate per-100g nutrition."""


class GenerationBlocked(RuntimeError):
    """Generation is off, unavailable, or over its daily cap."""


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #
def _daily_count(session: Session) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    return (
        session.execute(
            select(func.count(GenerationEvent.id)).where(GenerationEvent.created_at >= since)
        ).scalar()
        or 0
    )


def can_generate(session: Session) -> bool:
    if not settings.GENERATION_ENABLED or not is_enabled():
        return False
    return _daily_count(session) < settings.GENERATION_DAILY_CAP


# --------------------------------------------------------------------------- #
# Vocabulary extension
# --------------------------------------------------------------------------- #
def _ingredient_is_plausible(item: NewIngredient) -> Optional[str]:
    """None if the proposed ingredient is safe to store, else why it isn't.

    A hallucinated per_100g is not a cosmetic problem: it becomes the basis for
    the nutrition of every recipe that later uses this ingredient.
    """
    if not item.name.strip():
        return "empty name"
    if item.category not in INGREDIENT_CATEGORIES:
        return f"unknown category {item.category!r}"
    if item.default_unit not in INGREDIENT_UNITS:
        return f"unknown unit {item.default_unit!r}"
    if set(item.allergens) - ALLERGEN_SET:
        return f"off-vocab allergens {sorted(set(item.allergens) - ALLERGEN_SET)}"
    if item.vegan and not item.vegetarian:
        return "vegan but not vegetarian"
    m = item.per_100g
    if m.calories > settings.GENERATION_MAX_KCAL_PER_100G:
        return f"{m.calories} kcal/100g"
    if max(m.protein_g, m.carbs_g, m.fat_g) > settings.GENERATION_MAX_MACRO_PER_100G:
        return "a macro exceeds 100 g per 100 g"
    # Macros must roughly account for the calories, or the entry is internally
    # inconsistent however plausible each number looks alone.
    implied = 4 * m.protein_g + 4 * m.carbs_g + 9 * m.fat_g
    if m.calories and abs(implied - m.calories) > 0.5 * m.calories:
        return f"macros imply {implied:.0f} kcal, not {m.calories:.0f}"
    if item.grams_per_piece > 2000:
        return f"grams_per_piece {item.grams_per_piece}"
    return None


def _store_new_ingredients(
    session: Session, proposed: Iterable[NewIngredient]
) -> tuple[dict[str, int], list[str]]:
    """Insert plausible new canonicals. Returns (name -> id, rejection reasons)."""
    existing = {
        normalize(i.name): i
        for i in session.execute(select(Ingredient)).scalars()
    }
    added: dict[str, int] = {}
    rejected: list[str] = []
    for item in proposed:
        key = normalize(item.name)
        if key in existing:
            continue
        why = _ingredient_is_plausible(item)
        if why:
            rejected.append(f"{item.name}: {why}")
            continue
        row = Ingredient(
            name=key,
            category=item.category,
            aliases=[normalize(a) for a in item.aliases if a.strip()],
            vegetarian=item.vegetarian,
            vegan=item.vegan,
            allergens=clean_allergens(item.allergens),
            per_100g=item.per_100g.model_dump(),
            default_unit=item.default_unit,
            grams_per_unit=1 if item.default_unit in ("g", "ml") else item.grams_per_piece,
            grams_per_piece=item.grams_per_piece,
        )
        session.add(row)
        session.flush()
        existing[key] = row
        added[key] = row.id
    return added, rejected


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
def _exemplars(session: Session, cuisines: list[str], limit: int = 4) -> list[Recipe]:
    """Real recipes from the requested cuisine, to ground the model's output.

    Generation without them drifts toward generic restaurant food; with them a
    regional dish borrows the techniques the corpus actually contains.
    """
    if not cuisines:
        return []
    top, region = parse_cuisine_id(cuisines[0])
    query = select(Recipe).where(Recipe.cuisine == top)
    if region:
        query = query.where(Recipe.region == region)
    return list(session.execute(query.limit(limit)).scalars())


def _build_prompt(
    session: Session, req: RecommendRequest, pantry: list[str], vocabulary: list[str]
) -> str:
    lines = [f"Write {settings.GENERATION_MAX_RECIPES} distinct recipes that satisfy ALL of:"]
    if req.diet:
        lines.append(f"- Diet (absolute): {req.diet}")
    if req.exclude_allergens:
        lines.append(f"- Must not contain (absolute): {', '.join(req.exclude_allergens)}")
    if req.cuisines:
        lines.append(f"- Cuisine: {', '.join(label_for(c) for c in req.cuisines)}")
    if req.meal_type:
        lines.append(f"- Meal: {req.meal_type}")
    if req.max_time_minutes:
        lines.append(f"- Ready within {req.max_time_minutes} minutes")
    for goal in req.nutrition_goals:
        lines.append(f"- Nutrition goal: {goal.replace('_', ' ')} (as much as the dish allows)")
    if req.disliked_ingredients:
        lines.append(f"- Never include: {', '.join(req.disliked_ingredients)}")
    if pantry:
        lines.append(f"\nThe cook already has, prefer these where they fit: {', '.join(pantry)}")

    examples = _exemplars(session, req.cuisines)
    if examples:
        lines.append("\nReal recipes from this cuisine, for authenticity of technique:")
        for r in examples:
            names = ", ".join(i.get("name", "") for i in (r.ingredients or [])[:8])
            lines.append(f"- {r.title}: {names}")

    lines.append(
        "\nKnown ingredient vocabulary (use these exact names where they fit):\n"
        + ", ".join(vocabulary)
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Persist
# --------------------------------------------------------------------------- #
def _line_measure(line) -> str:
    return f"{line.qty if line.qty is not None else ''} {line.unit or ''}".strip()


def _violations(derived: dict, req: RecommendRequest) -> list[str]:
    """Where the recipe's DERIVED labels contradict what was asked for."""
    problems: list[str] = []
    if req.diet and req.diet not in derived["diet_labels"]:
        problems.append(f"not {req.diet} (derived: {derived['diet_labels']})")
    bad = sorted(set(req.exclude_allergens) & set(derived["allergens"]))
    if bad:
        problems.append(f"contains excluded allergen(s): {', '.join(bad)}")
    return problems


def _duplicate_of(session: Session, vector: list[float]) -> Optional[int]:
    row = session.execute(
        select(Recipe.id, Recipe.embedding.cosine_distance(vector).label("d"))
        .where(Recipe.embedding.isnot(None))
        .order_by("d")
        .limit(1)
    ).first()
    if row and row.d is not None and row.d < settings.GENERATION_DEDUP_DISTANCE:
        return row.id
    return None


def _persist(
    session: Session, gen: GeneratedRecipe, req: RecommendRequest, props: dict
) -> tuple[Optional[Recipe], list[str]]:
    """Validate against derived ground truth, then store. Returns (recipe, violations)."""
    name_to_id = {
        normalize(i.name): i.id for i in session.execute(select(Ingredient)).scalars()
    }

    matched: list[tuple] = []
    raw_names: list[str] = []
    lines: list[dict] = []
    ingredient_rows: list[tuple[int, Optional[float], Optional[str], bool]] = []
    for line in gen.ingredients:
        key = normalize(line.name)
        raw_names.append(line.name)
        lines.append(
            {"name": key, "qty": line.qty, "unit": line.unit, "essential": line.essential}
        )
        if key in props:
            matched.append(
                (key, measure_to_grams(props, key, _line_measure(line)), line.essential)
            )
        iid = name_to_id.get(key)
        if iid is not None:
            ingredient_rows.append((iid, line.qty, line.unit, line.essential))

    derived = classify_and_derive(
        props, matched, raw_names, gen.servings, title=gen.title
    )
    problems = _violations(derived, req)
    if problems:
        return None, problems
    if not ingredient_rows:
        return None, ["no ingredient resolved to the canonical vocabulary"]

    # The request's cuisine id is authoritative, never the model's own label.
    # Asked for "asian/korean" it returns cuisine="korean", but Korean is a
    # region under asian in the taxonomy — storing the model's word makes the
    # recipe unmatchable by the very filter that asked for it. Same reason diet
    # labels are re-derived: taxonomy placement is ours to decide, not the
    # model's to assert.
    if req.cuisines:
        cuisine, region = parse_cuisine_id(req.cuisines[0])
    elif gen.cuisine in CUISINE_TAXONOMY:
        cuisine, region = gen.cuisine, (gen.region or None)
    else:
        cuisine, region = None, None
    search_text = " ".join([gen.title] + [row["name"] for row in lines])
    vector = get_embedder().embed([search_text])[0]

    existing_id = _duplicate_of(session, vector)
    if existing_id is not None:
        return session.get(Recipe, existing_id), []

    recipe = Recipe(
        title=gen.title,
        description=gen.description,
        ingredients=lines,
        steps=gen.steps,
        tags=[],
        diet_labels=derived["diet_labels"],
        allergens=derived["allergens"],
        cuisine=cuisine,
        region=region,
        meal_types=gen.meal_types or ([req.meal_type] if req.meal_type else []),
        time_minutes=gen.time_minutes,
        servings=gen.servings,
        nutrition=derived["nutrition"],
        search_text=search_text,
        embedding=vector,
        source="generated",
        attribution="Written for this request",
        nutrition_estimated=True,
    )
    session.add(recipe)
    session.flush()
    for iid, qty, unit, essential in ingredient_rows:
        session.add(
            RecipeIngredient(
                recipe_id=recipe.id, ingredient_id=iid,
                qty=qty, unit=unit, essential=essential,
            )
        )
    return recipe, []


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def generate_recipes(
    session: Session, req: RecommendRequest, pantry: list[str], user_key: Optional[str] = None
) -> list[int]:
    """Generate, validate and persist recipes for this request. Returns recipe ids.

    Never raises: a blocked, failed or fully-rejected generation returns [] and
    the caller falls back to retrieval alone.
    """
    if not can_generate(session):
        return []

    started = time.monotonic()
    violations: list[dict] = []
    degraded = False
    ids: list[int] = []
    try:
        props = load_props(session)
        prompt = _build_prompt(session, req, pantry, sorted(props))
        result = get_llm().generate_structured(
            messages=[{"role": "user", "content": f"{SYSTEM}\n\n{prompt}"}],
            schema=GenerationResult,
            model=settings.LLM_MODEL_MAIN,
            max_tokens=8000,
            timeout=settings.GENERATION_TIMEOUT_SECONDS,
        )

        added, rejected = _store_new_ingredients(session, result.new_ingredients)
        for reason in rejected:
            violations.append({"type": "ingredient_rejected", "detail": reason})
        if added:
            props = load_props(session)  # uncached, so new entries are visible now

        for gen in result.recipes[: settings.GENERATION_MAX_RECIPES]:
            recipe, problems = _persist(session, gen, req, props)
            if problems:
                violations.extend(
                    {"type": "constraint", "recipe": gen.title, "detail": p} for p in problems
                )
                continue
            if recipe is not None:
                ids.append(recipe.id)
        session.commit()
    except LLMError as e:
        degraded = True
        violations.append({"type": "llm_error", "detail": str(e)})
        session.rollback()
        logger.warning("generation unavailable: %s", e)
    except Exception as e:  # never surface a generation fault to the caller
        degraded = True
        violations.append({"type": "error", "detail": repr(e)})
        session.rollback()
        logger.exception("generation failed")

    try:
        session.add(
            GenerationEvent(
                user_key=user_key,
                prompt_version=settings.PROMPT_VERSION,
                model=settings.LLM_MODEL_MAIN,
                violations=violations,
                repaired=False,
                degraded=degraded,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("could not log generation event")
    return ids
