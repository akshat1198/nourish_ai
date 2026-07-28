"""Last-resort per-serving nutrition for recipes the derivation can't compute.

Nutrition is normally summed from matched ingredient grams. That fails on rows
whose source measures are unrecoverable — a bone-in weight priced as breast
meat, a serving count that bears no relation to the quantities listed — and the
sum then lands outside the plausibility ceilings, where it is worse than
useless: ordering by a macro floats exactly those rows to the top.

Rather than leave those recipes with no nutrition at all, ask the model. What
comes back is treated like any other model assertion: range-checked against the
same ceilings a derived value must clear, and reconciled against itself, before
it is stored. An estimate that cannot clear the bar we just built for derived
values would only be laundering an implausible number past it.

Fails open. Every path returns None rather than raising, and a None leaves the
recipe exactly as it was — displayed, but without a nutrition block.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

from app.core.config import settings
from app.llm.client import LLMError, get_llm, is_enabled
from app.models import Recipe
from app.schemas.llm import EstimatedNutrition
from app.services.derivation import nutrition_usable, reconciles

logger = logging.getLogger(__name__)

_MACROS = ("calories", "protein_g", "carbs_g", "fat_g")

_SYSTEM = (
    "You estimate the nutrition of one home-cooked recipe from its ingredient "
    "list. Report PER SERVING, not for the whole dish.\n"
    "The stated serving count is often wrong — sources routinely claim 2 "
    "servings for a kilogram of meat. Judge how many people the listed "
    "quantities actually feed, divide by that, and report the number you used "
    "in `serves`.\n"
    "Assume ordinary home portions and ordinary ingredients. Where a quantity "
    "is missing, assume a normal amount for the dish rather than skipping it. "
    "Your four macro numbers must be consistent with each other: protein and "
    "carbohydrate are about 4 kcal per gram, fat about 9."
)


def _is_plausible(est: EstimatedNutrition) -> Optional[str]:
    """None if the estimate is safe to store, else why it isn't.

    Deliberately the same shape as generation._ingredient_is_plausible: the
    reason is logged, so a run that rejects a lot says what it was rejecting.
    """
    values = {k: getattr(est, k) for k in _MACROS}
    for key, value in values.items():
        if not math.isfinite(value) or value < 0:
            return f"{key}={value!r}"
    if values["calories"] <= 0:
        return "no calories"
    # The identical gate a derived value must pass. An estimate that only clears
    # a looser bar would defeat the ceilings rather than substitute for them.
    if not nutrition_usable(values):
        return (
            f"implausible per serving: {values['calories']:.0f} kcal, "
            f"{values['protein_g']:.0f}P/{values['carbs_g']:.0f}C/{values['fat_g']:.0f}F"
        )
    # Worth little against derived nutrition, which reconciles by construction,
    # but these four numbers were produced independently — this is where the
    # check earns its keep.
    if not reconciles(values, tolerance=0.5):
        implied = 4 * values["protein_g"] + 4 * values["carbs_g"] + 9 * values["fat_g"]
        return f"macros imply {implied:.0f} kcal, not {values['calories']:.0f}"
    return None


def _prompt(recipe: Recipe) -> str:
    """Title, claimed servings and the ingredient lines, and nothing else."""
    lines = []
    for item in recipe.ingredients or []:
        qty = item.get("qty")
        unit = (item.get("unit") or "").strip()
        name = item.get("name") or ""
        measure = " ".join(str(p) for p in (qty, unit) if p not in (None, ""))
        lines.append(f"- {measure} {name}".replace("-  ", "- "))
    return (
        f"Recipe: {recipe.title}\n"
        f"Claimed servings: {recipe.servings}\n"
        f"Ingredients:\n" + "\n".join(lines)
    )


def estimate_nutrition(recipe: Recipe) -> Optional[EstimatedNutrition]:
    """Per-serving macros for one recipe, or None if we can't stand behind any.

    Never raises. A None means the caller should leave the recipe's nutrition
    alone rather than substitute a number nobody has checked.
    """
    if not is_enabled():
        return None
    try:
        est = get_llm().generate_structured(
            messages=[{"role": "user", "content": f"{_SYSTEM}\n\n{_prompt(recipe)}"}],
            schema=EstimatedNutrition,
            model=settings.LLM_MODEL_FAST,
        )
    except LLMError as e:
        logger.warning("nutrition estimate failed for recipe %s: %s", recipe.id, e)
        return None
    reason = _is_plausible(est)
    if reason:
        # No retry-with-nudge: a model that returned 4,000 kcal for a dal is not
        # one round-trip from being right, and retrying is how a one-time
        # backfill turns into an unbounded spend.
        logger.warning("rejected nutrition estimate for recipe %s: %s", recipe.id, reason)
        return None
    return est


def as_nutrition(est: EstimatedNutrition) -> dict:
    """The stored per-serving shape, matching what classify_and_derive writes."""
    return {k: round(float(getattr(est, k)), 1) for k in _MACROS}
