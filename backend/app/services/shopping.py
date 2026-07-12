"""Shopping list composition (API-03).

Given chosen recipes and the user's pantry, aggregate every ingredient the
recipes need but the pantry lacks. Quantities are summed per (ingredient,
unit); mixed units for the same ingredient stay as separate rows (naive by
design — no unit-conversion library). A missing source quantity makes that
row's total unknown (null) rather than silently dropping it.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Ingredient, Recipe
from app.schemas.shopping import ShoppingItem, ShoppingListResponse
from app.services.ingredients import resolve_pantry


def build_shopping_list(
    session: Session, recipe_ids: list[int], pantry: list[str]
) -> ShoppingListResponse:
    resolved = resolve_pantry(session, pantry)
    pantry_set = set(resolved.ingredient_ids)

    recipes = (
        session.execute(
            select(Recipe)
            .where(Recipe.id.in_(recipe_ids))
            .options(selectinload(Recipe.recipe_ingredients))
        )
        .scalars()
        .all()
    )
    found_ids = {r.id for r in recipes}
    missing_recipe_ids = [rid for rid in recipe_ids if rid not in found_ids]

    id_to_name = {
        ing.id: ing.name for ing in session.execute(select(Ingredient)).scalars()
    }

    # (name, unit) -> aggregated row
    agg: dict[tuple[str, str | None], dict] = {}
    for recipe in recipes:
        for ri in recipe.recipe_ingredients:
            if ri.ingredient_id in pantry_set:
                continue
            name = id_to_name.get(ri.ingredient_id, "unknown")
            key = (name, ri.unit)
            row = agg.setdefault(
                key, {"total": 0.0, "qty_known": True, "recipes": []}
            )
            if ri.qty is None:
                row["qty_known"] = False
            else:
                row["total"] += float(ri.qty)
            if recipe.title not in row["recipes"]:
                row["recipes"].append(recipe.title)

    items = [
        ShoppingItem(
            name=name,
            unit=unit,
            total_qty=round(row["total"], 2) if row["qty_known"] else None,
            needed_for=row["recipes"],
        )
        for (name, unit), row in sorted(agg.items(), key=lambda kv: kv[0][0])
    ]

    return ShoppingListResponse(
        items=items,
        unmatched_pantry=resolved.unmatched,
        missing_recipe_ids=missing_recipe_ids,
    )
