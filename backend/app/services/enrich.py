"""Lazy recipe enrichment (WS6): rewrite terse steps + fill blank measures.

Runs on first view and caches to recipes.steps_rich / ingredients_rich, so it's
computed once per recipe (globally shared, never per-user, never re-run). Fails
open: if the assistant is unavailable or drifts, returns the originals with
enriched=False and stores nothing."""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.llm.client import LLMError, get_llm, is_enabled
from app.models import Ingredient, Recipe
from app.schemas.llm import EnrichedRecipe
from app.schemas.recipe import RecipeEnrichment, RecipeIngredientLine
from app.services.ingredients import normalize

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You improve a recipe WITHOUT changing what's made. Do two things:\n"
    "1) Rewrite the method into clear, correctly-ordered cooking steps. Add prep "
    "state (finely diced, thinly sliced, minced) and concrete cues (heat level, "
    "rough timing, the visual sign of doneness). Fix obvious transcription typos "
    "(e.g. 'steal the paneer' → 'strain the paneer'). DROP lines that aren't real "
    "cooking instructions — side notes like 'you can also buy it from outside', "
    "repeated serving blurbs, or links. You may merge redundant micro-steps. NEVER "
    "invent ingredients or add steps: the result must have AT MOST the original "
    "number of steps, in order; one or two sentences each.\n"
    "2) For each listed measure-less ingredient, give a typical amount for this "
    "dish as a short measure like '1 teaspoon' or '2 tablespoons', or 'to taste' "
    "for things like salt — in the SAME order as listed."
)

# leading number: "2", "1.5", "1/2", or "1 1/2"
_NUM = re.compile(r"^\s*(\d+\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+|\d+(?:\.\d+)?)\s*(.*)$")


def _has_measure(item: dict) -> bool:
    return item.get("qty") is not None or bool((item.get("unit") or "").strip())


def _parse_measure(s: str) -> tuple[Optional[float], str]:
    """'1 teaspoon' -> (1.0, 'teaspoon'); 'to taste' -> (None, 'to taste')."""
    s = (s or "").strip()
    m = _NUM.match(s)
    if not m:
        return None, s
    num, unit = m.group(1), m.group(2).strip()
    try:
        parts = num.split()
        if len(parts) == 2:  # "1 1/2"
            a, b = parts[1].split("/")
            val = float(parts[0]) + float(a) / float(b)
        elif "/" in num:  # "1/2"
            a, b = num.split("/")
            val = float(a) / float(b)
        else:
            val = float(num)
    except (ValueError, ZeroDivisionError):
        return None, s
    return round(val, 3), unit


def _category_map(session: Session, recipe: Recipe) -> dict[str, str]:
    ids = [ri.ingredient_id for ri in recipe.recipe_ingredients]
    if not ids:
        return {}
    cat: dict[str, str] = {}
    for ing in session.execute(select(Ingredient).where(Ingredient.id.in_(ids))).scalars():
        cat[normalize(ing.name)] = ing.category
        for alias in ing.aliases or []:
            cat.setdefault(normalize(alias), ing.category)
    return cat


def _build(steps: list[str], items: list[dict], cat: dict[str, str], enriched: bool) -> RecipeEnrichment:
    lines = [
        RecipeIngredientLine(
            name=it.get("name", ""),
            qty=it.get("qty"),
            unit=it.get("unit"),
            essential=it.get("essential", True),
            category=cat.get(normalize(it.get("name", ""))),
        )
        for it in items
    ]
    return RecipeEnrichment(steps=steps, ingredients=lines, enriched=enriched)


def enrich_recipe(session: Session, recipe_id: int) -> RecipeEnrichment:
    recipe = session.get(
        Recipe, recipe_id, options=[selectinload(Recipe.recipe_ingredients)]
    )
    if recipe is None:
        raise HTTPException(404, "recipe not found")

    cat = _category_map(session, recipe)

    # Already enriched (any prior viewer) — serve the cache, no LLM.
    if recipe.steps_rich is not None:
        items = recipe.ingredients_rich or recipe.ingredients or []
        return _build(recipe.steps_rich, items, cat, enriched=True)

    items = recipe.ingredients or []
    if not is_enabled():
        return _build(recipe.steps or [], items, cat, enriched=False)

    steps = recipe.steps or []
    measure_less = [i.get("name", "") for i in items if not _has_measure(i)]
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))
    prompt = (
        f"{_SYSTEM}\n\nTitle: {recipe.title}\n"
        f"Ingredients: {', '.join(i.get('name', '') for i in items)}\n"
        f"Measure-less ingredients (give an amount for each, in order): "
        f"{', '.join(measure_less) if measure_less else '(none)'}\n"
        f"Method ({len(steps)} steps):\n{numbered}"
    )
    try:
        result = get_llm().generate_structured(
            messages=[{"role": "user", "content": prompt}],
            schema=EnrichedRecipe,
            model=settings.LLM_MODEL_MAIN,
            max_tokens=2200,
        )
    except LLMError as e:
        logger.warning("recipe enrichment failed (%s): %s", recipe_id, e)
        return _build(steps, items, cat, enriched=False)

    new_steps = [s.strip() for s in result.steps if s.strip()]
    # Cleaning may DROP junk lines (fewer steps is fine); reject only empty output
    # or invented extra steps (more than the original).
    if not new_steps or len(new_steps) > len(steps):
        new_steps = steps

    fills: dict[str, str] = {}
    for name, meas in zip(measure_less, result.quantities):
        fills.setdefault(name, meas)
    rich_items: list[dict] = []
    for it in items:
        it = dict(it)
        name = it.get("name", "")
        if not _has_measure(it) and name in fills:
            it["qty"], it["unit"] = _parse_measure(fills[name])
        rich_items.append(it)

    recipe.steps_rich = new_steps
    recipe.ingredients_rich = rich_items
    session.commit()
    return _build(new_steps, rich_items, cat, enriched=True)
