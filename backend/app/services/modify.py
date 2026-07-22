"""Substitution-aware recipe modification.

Deterministic core: apply a table-grounded ingredient swap (ratio-scaled
quantities) and re-derive diet/allergen on the post-swap canonical set via the
shared `derivation` module — so a swap can never silently keep a stale allergen
label. Swaps must exist in the `substitutions` table (the safety property).

Steps pass through unchanged here; the LLM rewrite is layered on in 7.3c.
Nutrition is NOT recomputed (a warning says so). Nothing is persisted.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.llm.client import LLMError, get_llm, is_enabled
from app.models import Ingredient, Recipe, Substitution
from app.schemas.llm import FreeSwapAdaptation, ModifiedSteps, RemovalPlan
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


_FREESWAP_SYSTEM = (
    "You adapt a recipe to substitute ONE ingredient with another that is NOT in "
    "our database, so estimate carefully and conservatively. Given the numbered "
    "steps (0-indexed), the ingredient list, and the swap, return: a quantity "
    "ratio (original:substitute), ONLY the steps that change (by original index, "
    "matching the original wording and style), knock-on effects, any allergens "
    "the new ingredient adds or removes, diets it enables or breaks, and an "
    "approximate signed per-serving nutrition delta (omit if genuinely unsure)."
)


def _apply_freetext_swap(
    session: Session, recipe: Recipe, from_name: str, from_keys: set[str], to_name: str
) -> ModifyResponse:
    """Swap where a side is outside our vocabulary — the target OR the source (a
    source-worded display name like "cheese"). The LLM estimates the ratio, step
    edits, allergen/diet effects, and nutrition delta. Flagged approximate."""
    if not is_enabled():
        raise HTTPException(
            422,
            f"'{to_name}' isn't a known ingredient, and the recipe assistant "
            "needed to adapt to it isn't configured.",
        )

    steps = recipe.steps or []
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(steps))
    ing_list = "; ".join(
        f"{_measure_str(l)} {l.get('name', '')}".strip() for l in (recipe.ingredients or [])
    )
    prompt = (
        f"{_FREESWAP_SYSTEM}\n\n"
        f'Swap: replace "{from_name}" with "{to_name}".\n'
        f"Title: {recipe.title}\nIngredients: {ing_list}\nSteps:\n{numbered}"
    )
    try:
        adapt = get_llm().generate_structured(
            messages=[{"role": "user", "content": prompt}],
            schema=FreeSwapAdaptation,
            model=settings.LLM_MODEL_MAIN,
            max_tokens=1600,
        )
    except LLMError as e:
        logger.warning("free-text swap adaptation failed: %s", e)
        raise HTTPException(503, "Couldn't adapt this swap right now — try again.")

    multiplier, ratio_ok = _parse_ratio(adapt.ratio)

    # Category dots for the unchanged display lines (the free-text line has none).
    cat_by_norm: dict[str, str] = {}
    for ing in session.execute(select(Ingredient)).scalars():
        cat_by_norm.setdefault(normalize(ing.name), ing.category)
        for a in ing.aliases or []:
            cat_by_norm.setdefault(normalize(a), ing.category)

    new_lines: list[dict] = []
    for item in recipe.ingredients or []:
        line = dict(item)
        if normalize(line.get("name", "")) in from_keys:
            line["name"] = to_name
            if line.get("qty") is not None:
                line["qty"] = round(float(line["qty"]) * multiplier, 2)
        new_lines.append(line)

    to_norm = normalize(to_name)
    lines_out = [
        RecipeIngredientLine(
            name=l.get("name", ""),
            qty=l.get("qty"),
            unit=l.get("unit"),
            essential=l.get("essential", True),
            category=None
            if normalize(l.get("name", "")) == to_norm
            else cat_by_norm.get(normalize(l.get("name", ""))),
        )
        for l in new_lines
    ]

    new_steps = list(steps)
    changed: list[int] = []
    for st in adapt.changed_steps:
        if 0 <= st.index < len(new_steps):
            new_steps[st.index] = st.text
            changed.append(st.index)

    old_all = set(recipe.allergens or [])
    added, removed = set(adapt.added_allergens), set(adapt.removed_allergens)
    new_allergens = sorted((old_all | added) - removed)

    diet = [d for d in (recipe.diet_labels or []) if d not in adapt.breaks_diets]
    for d in adapt.enables_diets:
        if d not in diet:
            diet.append(d)

    baseline = recipe.nutrition or {}
    nutrition: dict = {}
    nutrition_delta: dict = {}
    if adapt.nutrition_delta and baseline:
        d = adapt.nutrition_delta
        nutrition_delta = {k: round(getattr(d, k), 1) for k in _MACROS if k in baseline}
        nutrition = {
            k: max(0.0, round(baseline[k] + nutrition_delta[k], 1))
            for k in baseline
            if k in nutrition_delta
        }

    warnings = [
        "Estimated — this swap involves an ingredient outside our verified data, "
        "so labels and nutrition are approximate."
    ]
    if not nutrition:
        warnings.append(NUTRITION_WARNING)
    if not ratio_ok:
        warnings.append(f"Couldn't read the ratio '{adapt.ratio}'; kept quantities unchanged.")

    return ModifyResponse(
        recipe_id=recipe.id,
        title=recipe.title,
        swap=SwapInfo(from_ingredient=from_name, to_ingredient=to_name, ratio=adapt.ratio),
        ingredients=lines_out,
        steps=new_steps,
        changed_step_indexes=sorted(set(changed)),
        diet_labels=diet,
        allergens=new_allergens,
        added_allergens=sorted(added - old_all),
        removed_allergens=sorted(removed & old_all),
        nutrition=nutrition,
        nutrition_delta=nutrition_delta,
        knock_on_flags=adapt.knock_on_flags,
        warnings=warnings,
        llm_used=True,
        approximate=True,
    )


_REMOVE_SYSTEM = (
    "You adapt a recipe when the cook wants ONE ingredient GONE. Choose the "
    "strategy that keeps the dish working: 'substitute' with the best common "
    "alternative when the ingredient is important (e.g. a binder or fat), or "
    "'omit' when it's safe to just leave out. Return: the strategy, the "
    "substitute (if any) with a removed:substitute ratio, ONLY the steps that "
    "change (by original 0-based index, matching wording/style), knock-on "
    "effects, allergen/diet changes, an approximate signed per-serving nutrition "
    "delta, and a one-line note on what you did and how to compensate."
)


def _category_map(session: Session) -> dict[str, str]:
    cat: dict[str, str] = {}
    for ing in session.execute(select(Ingredient)).scalars():
        cat.setdefault(normalize(ing.name), ing.category)
        for a in ing.aliases or []:
            cat.setdefault(normalize(a), ing.category)
    return cat


def _subtract_nutrition(
    props: dict, baseline: dict, from_name: str, from_keys: set[str],
    orig_lines: list[dict], servings: int,
) -> tuple[dict, dict]:
    """Per-serving nutrition after simply removing an ingredient: subtract its
    contribution from the baseline. ({}, {}) when it can't be estimated."""
    from_per = props.get(from_name, {}).get("per_100g")
    if not baseline or not from_per:
        return {}, {}
    total = {k: 0.0 for k in _MACROS}
    for orig in orig_lines:
        if normalize(orig.get("name", "")) not in from_keys:
            continue
        g = measure_to_grams(props, from_name, _measure_str(orig))
        for k in _MACROS:
            total[k] -= from_per.get(k, 0) * g / 100
    s = max(1, servings)
    delta = {k: round(total[k] / s, 1) for k in _MACROS if k in baseline}
    estimated = {k: max(0.0, round(baseline[k] + delta[k], 1)) for k in baseline if k in delta}
    return estimated, delta


def _apply_remove(
    session: Session,
    recipe: Recipe,
    from_name: str,
    from_keys: set[str],
    from_ing: Optional[Ingredient],
    index: dict,
    id_to_name: dict[int, str],
) -> ModifyResponse:
    """Remove an ingredient — a SMALL LLM call decides omit vs substitute and
    rewrites the affected steps; allergens/diet/nutrition are re-derived in code
    (accurate + keeps the constrained-decoding grammar small so it doesn't time
    out). `from_ing` is None for a source-worded display name outside our vocab
    (e.g. "cheese"); then labels are left conservatively unchanged (approximate)."""
    if not is_enabled():
        raise HTTPException(
            422,
            f"Removing “{from_name}” needs the recipe assistant, which isn't configured.",
        )

    steps = recipe.steps or []
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(steps))
    ing_list = "; ".join(
        f"{_measure_str(l)} {l.get('name', '')}".strip() for l in (recipe.ingredients or [])
    )
    prompt = (
        f"{_REMOVE_SYSTEM}\n\n"
        f'Remove: "{from_name}".\n'
        f"Title: {recipe.title}\nIngredients: {ing_list}\nSteps:\n{numbered}"
    )
    try:
        plan = get_llm().generate_structured(
            messages=[{"role": "user", "content": prompt}],
            schema=RemovalPlan,
            model=settings.LLM_MODEL_MAIN,
            max_tokens=1200,
        )
    except LLMError as e:
        logger.warning("remove adaptation failed: %s", e)
        raise HTTPException(503, "Couldn't adjust the recipe right now — try again.")

    substituting = plan.strategy.strip().lower().startswith("sub") and bool(
        plan.substitute.strip()
    )
    to_name = plan.substitute.strip() if substituting else ""
    to_ing = index.get(normalize(to_name)) if substituting else None
    multiplier, ratio_ok = _parse_ratio(plan.ratio) if substituting else (1.0, True)
    cat_by_norm = _category_map(session)

    # Rewrite the display lines: rename+scale if substituting, else drop the line.
    new_lines: list[dict] = []
    for item in recipe.ingredients or []:
        if normalize(item.get("name", "")) in from_keys:
            if not substituting:
                continue  # omit: the line disappears
            line = dict(item)
            line["name"] = to_name
            if line.get("qty") is not None:
                line["qty"] = round(float(line["qty"]) * multiplier, 2)
            new_lines.append(line)
        else:
            new_lines.append(dict(item))

    lines_out = [
        RecipeIngredientLine(
            name=l.get("name", ""),
            qty=l.get("qty"),
            unit=l.get("unit"),
            essential=l.get("essential", True),
            category=cat_by_norm.get(normalize(l.get("name", ""))),
        )
        for l in new_lines
    ]

    new_steps = list(steps)
    changed: list[int] = []
    for st in plan.changed_steps:
        if 0 <= st.index < len(new_steps):
            new_steps[st.index] = st.text
            changed.append(st.index)

    # Re-derive diet/allergen deterministically on the post-removal canonical set.
    props = load_props()
    post_names: list[str] = []
    post_items: list[tuple] = []
    for ri in recipe.recipe_ingredients:
        if from_ing is not None and ri.ingredient_id == from_ing.id:
            if substituting and to_ing is not None:
                name = to_ing.name  # canonical substitute
            else:
                continue  # omit, or a free-text substitute we can't classify
        else:
            name = id_to_name.get(ri.ingredient_id, "unknown")
        post_names.append(name)
        if name in props:
            post_items.append((name, 1.0, ri.essential))
    derived = classify_and_derive(
        props, post_items, post_names, servings=recipe.servings, title=recipe.title
    )
    new_allergens = derived["allergens"]
    old_all = set(recipe.allergens or [])

    # Nutrition: exact-ish for omit / canonical substitute; skipped for unknown.
    baseline = recipe.nutrition or {}
    if substituting and to_ing is not None:
        nutrition, nutrition_delta = _nutrition_estimate(
            props, baseline, from_name, to_ing.name, from_keys,
            recipe.ingredients or [], new_lines, recipe.servings,
        )
    elif not substituting:
        # _subtract_nutrition returns ({}, {}) when from_name isn't in our props
        # (e.g. a non-canonical display name) — honest and safe.
        nutrition, nutrition_delta = _subtract_nutrition(
            props, baseline, from_name, from_keys, recipe.ingredients or [], recipe.servings
        )
    else:
        nutrition, nutrition_delta = {}, {}

    # Approximate when the source isn't canonical (labels can't be re-derived) or
    # the substitute is a free-text one; omit/canonical re-derive from our data.
    approximate = from_ing is None or (substituting and to_ing is None)
    warnings: list[str] = []
    if approximate:
        unknown = from_name if from_ing is None else to_name
        warnings.append(
            f"Estimated — “{unknown}” isn't in our verified data, so labels and "
            "nutrition are approximate."
        )
    if not nutrition:
        warnings.append(NUTRITION_WARNING)

    return ModifyResponse(
        recipe_id=recipe.id,
        title=recipe.title,
        operation="remove",
        note=plan.note,
        swap=SwapInfo(
            from_ingredient=from_name,
            to_ingredient=to_name or "(removed)",
            ratio=plan.ratio if substituting else "—",
        ),
        ingredients=lines_out,
        steps=new_steps,
        changed_step_indexes=sorted(set(changed)),
        diet_labels=derived["diet_labels"],
        allergens=new_allergens,
        added_allergens=sorted(set(new_allergens) - old_all),
        removed_allergens=sorted(old_all - set(new_allergens)),
        nutrition=nutrition,
        nutrition_delta=nutrition_delta,
        knock_on_flags=plan.knock_on_flags,
        warnings=warnings,
        llm_used=True,
        approximate=approximate,
    )


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
    from_norm = normalize(req.from_ingredient)
    recipe_ing_ids = {ri.ingredient_id for ri in recipe.recipe_ingredients}
    display_names = {normalize(l.get("name", "")) for l in (recipe.ingredients or [])}

    # The from-ingredient must be one the recipe actually lists — either by its
    # canonical id, OR (for source-worded display names like "cheese"/"oil" that
    # don't map to our vocabulary) by matching a display line. Non-canonical
    # sources are handled via the LLM path below.
    in_canon = from_ing is not None and from_ing.id in recipe_ing_ids
    if not in_canon and from_norm not in display_names:
        raise HTTPException(422, f"recipe does not use {req.from_ingredient}")

    from_name = from_ing.name if in_canon else req.from_ingredient.strip()
    from_keys = (
        {normalize(from_ing.name)} | {normalize(a) for a in from_ing.aliases or []}
        if in_canon
        else {from_norm}
    )
    from_canon = from_ing if in_canon else None

    if req.op == "remove":
        return _apply_remove(session, recipe, from_name, from_keys, from_canon, index, id_to_name)

    if not req.to_ingredient:
        raise HTTPException(422, "to_ingredient is required for a swap")

    to_ing = index.get(normalize(req.to_ingredient))
    # LLM (approximate) path when EITHER side is outside our vocabulary — an
    # unknown target (e.g. "dahi") or a non-canonical source display name.
    if to_ing is None or from_canon is None:
        return _apply_freetext_swap(
            session, recipe, from_name, from_keys, req.to_ingredient.strip()
        )

    # Deterministic path: both canonical, source in the recipe. Prefer a curated
    # ratio when we have one; otherwise 1:1 (any canonical target is valid).
    sub = session.execute(
        select(Substitution).where(
            Substitution.ingredient_id == from_canon.id,
            Substitution.substitute_id == to_ing.id,
        )
    ).scalar_one_or_none()
    ratio_str = sub.ratio if sub else "1:1"
    multiplier, ratio_ok = _parse_ratio(ratio_str)

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
        recipe.title, recipe.steps or [], from_ing.name, to_ing.name, ratio_str
    )

    warnings: list[str] = []
    if not ratio_ok:
        warnings.append(
            f"Couldn't read the substitution ratio '{ratio_str}'; kept quantities unchanged."
        )
    warnings.extend(step_warnings)
    if not nutrition:
        # Couldn't estimate (no baseline or missing props) — be honest.
        warnings.append(NUTRITION_WARNING)

    return ModifyResponse(
        recipe_id=recipe.id,
        title=recipe.title,
        swap=SwapInfo(
            from_ingredient=from_ing.name, to_ingredient=to_ing.name, ratio=ratio_str
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
        approximate=False,
    )
