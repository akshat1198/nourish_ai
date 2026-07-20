"""Substitution-aware recipe modification (Stage 7.3).

Deterministic core: apply a table-grounded ingredient swap (ratio-scaled
quantities) and re-derive diet/allergen on the post-swap canonical set via the
shared `derivation` module — so a swap can never silently keep a stale allergen
label. Swaps must exist in the `substitutions` table (the safety property).

Steps pass through unchanged here; the LLM rewrite is layered on in 7.3c.
Nutrition is NOT recomputed (a warning says so). Nothing is persisted.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Ingredient, Recipe, Substitution
from app.schemas.recipe import ModifyRequest, ModifyResponse, RecipeIngredientLine, SwapInfo
from app.services.derivation import classify_and_derive, load_props
from app.services.ingredients import normalize

NUTRITION_WARNING = "Nutrition still reflects the original recipe."


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

    warnings: list[str] = []
    if not ratio_ok:
        warnings.append(
            f"Couldn't read the substitution ratio '{sub.ratio}'; kept quantities unchanged."
        )
    warnings.append(NUTRITION_WARNING)

    return ModifyResponse(
        recipe_id=recipe.id,
        title=recipe.title,
        swap=SwapInfo(
            from_ingredient=from_ing.name, to_ingredient=to_ing.name, ratio=sub.ratio
        ),
        ingredients=lines_out,
        steps=recipe.steps or [],
        changed_step_indexes=[],
        diet_labels=derived["diet_labels"],
        allergens=new_allergens,
        added_allergens=added,
        removed_allergens=removed,
        knock_on_flags=[],
        warnings=warnings,
        llm_used=False,
    )
