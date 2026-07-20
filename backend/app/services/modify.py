"""Substitution-aware recipe modification (Stage 7.3).

Deterministic core: apply a table-grounded ingredient swap (ratio-scaled
quantities) and re-derive diet/allergen on the post-swap canonical set via the
shared `derivation` module — so a swap can never silently keep a stale allergen
label. Swaps must exist in the `substitutions` table (the safety property).

Steps pass through unchanged here; the LLM rewrite is layered on in 7.3c.
Nutrition is NOT recomputed (a warning says so). Nothing is persisted.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.llm.client import LLMError, get_llm, is_enabled
from app.models import Ingredient, Recipe, Substitution
from app.schemas.llm import ModifiedSteps
from app.schemas.recipe import ModifyRequest, ModifyResponse, RecipeIngredientLine, SwapInfo
from app.services.derivation import classify_and_derive, load_props, measure_to_grams
from app.services.ingredients import normalize

logger = logging.getLogger(__name__)

NUTRITION_WARNING = "Nutrition still reflects the original recipe."
_MACROS = ("calories", "protein_g", "carbs_g", "fat_g")


def _measure_str(line: dict) -> str:
    qty = line.get("qty")
    unit = line.get("unit") or ""
    return f"{qty} {unit}".strip() if qty is not None else unit


def _nutrition_estimate(
    props: dict,
    baseline: dict,
    from_name: str,
    to_name: str,
    from_keys: set[str],
    orig_lines: list[dict],
    new_lines: list[dict],
    servings: int,
) -> tuple[dict, dict]:
    """Estimate post-swap per-serving nutrition by applying the swapped
    ingredient's macro delta to the displayed baseline. Localized to the changed
    line(s) — the rest of the recipe is unchanged, so its contribution cancels.
    Returns ({}, {}) when it can't be estimated honestly."""
    from_per = props.get(from_name, {}).get("per_100g")
    to_per = props.get(to_name, {}).get("per_100g")
    if not baseline or not from_per or not to_per:
        return {}, {}

    total = {k: 0.0 for k in _MACROS}
    for orig, new in zip(orig_lines, new_lines):
        if normalize(orig.get("name", "")) not in from_keys:
            continue
        g_from = measure_to_grams(props, from_name, _measure_str(orig))
        g_to = measure_to_grams(props, to_name, _measure_str(new))
        for k in _MACROS:
            total[k] += (to_per.get(k, 0) * g_to - from_per.get(k, 0) * g_from) / 100

    s = max(1, servings)
    delta = {k: round(total[k] / s, 1) for k in _MACROS if k in baseline}
    estimated = {
        k: max(0.0, round(baseline[k] + delta[k], 1)) for k in baseline if k in delta
    }
    return estimated, delta
# Don't ask the model to rewrite pathologically long methods (cost + latency).
MAX_STEPS_FOR_LLM = 40

_STEP_SYSTEM = (
    "You adapt a recipe's method for a SINGLE ingredient substitution. You get "
    "the numbered steps (0-indexed) and the swap. Rewrite ONLY the steps that "
    "mention the original ingredient or its handling; leave every other step "
    "untouched and DO NOT renumber. Return each changed step with its original "
    "index and the new text, matching the original wording and style. Also list "
    "knock-on effects the cook should know (cooking time, texture, binding, "
    "seasoning, moisture)."
)


def _rewrite_steps(
    title: str, steps: list[str], from_name: str, to_name: str, ratio: str
) -> tuple[list[str], list[int], list[str], bool, list[str]]:
    """LLM step rewrite. Fail-open degraded: returns the original steps + a
    warning when the LLM is unavailable, never raising. Returns
    (steps, changed_indexes, knock_on_flags, llm_used, warnings)."""
    if not is_enabled():
        return steps, [], [], False, [
            "Steps weren't adjusted for the swap — the recipe assistant isn't configured."
        ]
    if len(steps) > MAX_STEPS_FOR_LLM:
        return steps, [], [], False, [
            "Steps weren't adjusted — this method is too long to rewrite reliably."
        ]

    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(steps))
    prompt = (
        f"{_STEP_SYSTEM}\n\n"
        f'Swap: replace "{from_name}" with "{to_name}" (ratio {ratio}).\n'
        f"Title: {title}\nSteps:\n{numbered}"
    )
    try:
        result = get_llm().generate_structured(
            messages=[{"role": "user", "content": prompt}],
            schema=ModifiedSteps,
            model=settings.LLM_MODEL_MAIN,
            max_tokens=2000,
        )
    except LLMError as e:
        logger.warning("modify step rewrite failed, showing original method: %s", e)
        return steps, [], [], False, [
            "Steps couldn't be adjusted for the swap; showing the original method."
        ]

    new_steps = list(steps)
    changed: list[int] = []
    for st in result.steps:
        if 0 <= st.index < len(new_steps):
            new_steps[st.index] = st.text
            changed.append(st.index)
    return new_steps, sorted(set(changed)), result.knock_on_flags, True, []


def _parse_ratio(ratio: str) -> tuple[float, bool]:
    """"a:b" -> b/a (how the substitute quantity scales). (1.0, False) if unparseable."""
    try:
        a, b = ratio.split(":")
        fa, fb = float(a), float(b)
        if fa > 0:
            return fb / fa, True
    except (ValueError, AttributeError):
        pass
    return 1.0, False


def modify_recipe(
    session: Session, recipe_id: int, req: ModifyRequest
) -> ModifyResponse:
    recipe = session.get(
        Recipe, recipe_id, options=[selectinload(Recipe.recipe_ingredients)]
    )
    if recipe is None:
        raise HTTPException(404, "recipe not found")

    # Resolve both names to canonical ingredients (name or alias).
    index: dict[str, Ingredient] = {}
    id_to_name: dict[int, str] = {}
    for ing in session.execute(select(Ingredient)).scalars():
        id_to_name[ing.id] = ing.name
        index.setdefault(normalize(ing.name), ing)
        for alias in ing.aliases or []:
            index.setdefault(normalize(alias), ing)

    from_ing = index.get(normalize(req.from_ingredient))
    to_ing = index.get(normalize(req.to_ingredient))
    if from_ing is None:
        raise HTTPException(422, f"unknown ingredient: {req.from_ingredient}")
    if to_ing is None:
        raise HTTPException(422, f"unknown ingredient: {req.to_ingredient}")

    # Table-grounded swaps only.
    sub = session.execute(
        select(Substitution).where(
            Substitution.ingredient_id == from_ing.id,
            Substitution.substitute_id == to_ing.id,
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            422, f"no known substitution from {from_ing.name} to {to_ing.name}"
        )

    # The recipe must actually use the from-ingredient (authoritative: the
    # canonical join, not the source-worded display list).
    recipe_ing_ids = {ri.ingredient_id for ri in recipe.recipe_ingredients}
    if from_ing.id not in recipe_ing_ids:
        raise HTTPException(422, f"recipe does not use {from_ing.name}")

    multiplier, ratio_ok = _parse_ratio(sub.ratio)
    from_keys = {normalize(from_ing.name)} | {
        normalize(a) for a in from_ing.aliases or []
    }

    # Rewrite matching display lines (best-effort for the UI).
    new_lines: list[dict] = []
    for item in recipe.ingredients or []:
        line = dict(item)
        if normalize(line.get("name", "")) in from_keys:
            line["name"] = to_ing.name
            if line.get("qty") is not None:
                line["qty"] = round(float(line["qty"]) * multiplier, 2)
        new_lines.append(line)

    # Re-derive diet/allergen on the post-swap canonical set.
    props = load_props()
    post_names: list[str] = []
    post_items: list[tuple] = []
    for ri in recipe.recipe_ingredients:
        name = to_ing.name if ri.ingredient_id == from_ing.id else id_to_name.get(
            ri.ingredient_id, "unknown"
        )
        post_names.append(name)
        if name in props:
            post_items.append((name, 1.0, ri.essential))
    derived = classify_and_derive(
        props, post_items, post_names, servings=recipe.servings, title=recipe.title
    )
    new_allergens = derived["allergens"]
    old_allergens = set(recipe.allergens or [])
    added = sorted(set(new_allergens) - old_allergens)
    removed = sorted(old_allergens - set(new_allergens))

    # Category dots for the (possibly renamed) display lines.
    cat_ids = recipe_ing_ids | {to_ing.id}
    cat: dict[str, str] = {}
    for ing in session.execute(
        select(Ingredient).where(Ingredient.id.in_(cat_ids))
    ).scalars():
        cat[normalize(ing.name)] = ing.category
        for alias in ing.aliases or []:
            cat.setdefault(normalize(alias), ing.category)
    lines_out = [
        RecipeIngredientLine(
            name=l.get("name", ""),
            qty=l.get("qty"),
            unit=l.get("unit"),
            essential=l.get("essential", True),
            category=cat.get(normalize(l.get("name", ""))),
        )
        for l in new_lines
    ]

    nutrition, nutrition_delta = _nutrition_estimate(
        props,
        recipe.nutrition or {},
        from_ing.name,
        to_ing.name,
        from_keys,
        recipe.ingredients or [],
        new_lines,
        recipe.servings,
    )

    steps_out, changed_idx, knock_flags, llm_used, step_warnings = _rewrite_steps(
        recipe.title, recipe.steps or [], from_ing.name, to_ing.name, sub.ratio
    )

    warnings: list[str] = []
    if not ratio_ok:
        warnings.append(
            f"Couldn't read the substitution ratio '{sub.ratio}'; kept quantities unchanged."
        )
    warnings.extend(step_warnings)
    if not nutrition:
        # Couldn't estimate (no baseline or missing props) — be honest.
        warnings.append(NUTRITION_WARNING)

    return ModifyResponse(
        recipe_id=recipe.id,
        title=recipe.title,
        swap=SwapInfo(
            from_ingredient=from_ing.name, to_ingredient=to_ing.name, ratio=sub.ratio
        ),
        ingredients=lines_out,
        steps=steps_out,
        changed_step_indexes=changed_idx,
        diet_labels=derived["diet_labels"],
        allergens=new_allergens,
        added_allergens=added,
        removed_allergens=removed,
        nutrition=nutrition,
        nutrition_delta=nutrition_delta,
        knock_on_flags=knock_flags,
        warnings=warnings,
        llm_used=llm_used,
    )
