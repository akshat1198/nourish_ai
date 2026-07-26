"""Recompute per-serving nutrition for every recipe from its resolved ingredients.

Needed after any change to ingredient gram weights or per_100g values: the
stored numbers are a snapshot of whatever the properties said at import time.

Only `nutrition` is written. diet_labels and allergens are deliberately left
alone — they are safety-bearing, were derived by the same function at import,
and silently churning them from a nutrition fix is exactly the kind of change
that should be its own reviewed pass.

Run from backend/ (DB must be up):
  ../.venv/bin/python -m scripts.rederive_nutrition --dry
  ../.venv/bin/python -m scripts.rederive_nutrition
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.models import Ingredient, Recipe
from app.services.derivation import classify_and_derive, load_props, measure_to_grams


def _reconciles(n: dict, tolerance: float = 0.3) -> bool:
    """Do the macros add up to the calorie total (4/4/9 kcal per gram)?

    A cheap internal-consistency check: it can't prove the grams are right, but
    it catches a macro being computed on a different basis from the total.
    """
    cal = n.get("calories", 0)
    if not cal:
        return True
    implied = 4 * n.get("protein_g", 0) + 4 * n.get("carbs_g", 0) + 9 * n.get("fat_g", 0)
    return abs(cal - implied) <= tolerance * cal


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="report only, no writes")
    ap.add_argument("--sample", type=int, default=5, help="before/after rows to print")
    ap.add_argument("--labels", action="store_true",
                    help="also rewrite diet_labels/allergens (safety-bearing; review the delta)")
    args = ap.parse_args()

    changed = 0
    emptied = 0
    inconsistent = 0
    samples: list[str] = []
    label_delta: list[tuple] = []

    with SessionLocal() as session:
        props = load_props(session)
        names = {i.id: i.name for i in session.execute(select(Ingredient)).scalars()}
        recipes = session.execute(
            select(Recipe).options(selectinload(Recipe.recipe_ingredients))
        ).scalars().all()
        print(f"re-deriving {len(recipes)} recipes...")

        for recipe in recipes:
            items = []
            for ri in recipe.recipe_ingredients:
                name = names.get(ri.ingredient_id)
                if name is None:
                    continue
                measure = f"{ri.qty if ri.qty is not None else ''} {ri.unit or ''}".strip()
                items.append((name, measure_to_grams(props, name, measure), ri.essential))

            raw_names = [i.get("name", "") for i in (recipe.ingredients or [])]
            derived = classify_and_derive(
                props, items, raw_names, recipe.servings, title=recipe.title
            )
            if args.labels:
                # Safety-bearing: only ever applied deliberately, and reported
                # as a delta so a label that DISAPPEARS is visible rather than
                # silently dropped.
                old_diet = set(recipe.diet_labels or [])
                # classify_and_derive only ever emits these five. Any other
                # label (pescatarian, on 31 rows) came from the source and is
                # not ours to drop just because we cannot re-derive it.
                DERIVED = {"vegan", "vegetarian", "gluten_free", "dairy_free", "nut_free"}
                new_diet = set(derived["diet_labels"]) | (old_diet - DERIVED)
                old_alg = set(recipe.allergens or [])
                new_alg = set(derived["allergens"])
                if old_diet != new_diet or old_alg != new_alg:
                    label_delta.append(
                        (recipe.title, sorted(new_diet - old_diet), sorted(old_diet - new_diet),
                         sorted(new_alg - old_alg), sorted(old_alg - new_alg))
                    )
                    recipe.diet_labels = sorted(new_diet)
                    recipe.allergens = sorted(new_alg)

            before, after = recipe.nutrition or {}, derived["nutrition"]
            if before == after:
                continue

            if not after:
                emptied += 1
            elif not _reconciles(after):
                inconsistent += 1
            if len(samples) < args.sample:
                samples.append(
                    f"  {recipe.title[:38]:40}\n"
                    f"     before {before}\n     after  {after}"
                )
            recipe.nutrition = after
            recipe.nutrition_estimated = True
            changed += 1

        if args.dry:
            session.rollback()
        else:
            session.commit()

    print(f"\nchanged {changed}{' (dry run)' if args.dry else ''}; "
          f"{emptied} now have no usable nutrition; "
          f"{inconsistent} do not reconcile with their calorie total")
    if args.labels:
        gained = sum(1 for d in label_delta if "vegan" in d[1])
        lost = sum(1 for d in label_delta if "vegan" in d[2])
        alg_removed = sum(1 for d in label_delta if d[4])
        print(f"\nlabel changes: {len(label_delta)} recipes; +vegan {gained}, -vegan {lost}, "
              f"allergen removed on {alg_removed}")
        for t, dg, dl, ag, al in label_delta[:6]:
            print(f"  {t[:44]:46} diet +{dg} -{dl}  allergen +{ag} -{al}")
    print("\nsample:")
    print("\n".join(samples))
    return 0


if __name__ == "__main__":
    sys.exit(main())
