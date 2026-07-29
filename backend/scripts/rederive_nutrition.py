"""Recompute per-serving nutrition for every recipe from its resolved ingredients.

Needed after any change to ingredient gram weights or per_100g values: the
stored numbers are a snapshot of whatever the properties said at import time.

Only `nutrition` is written. diet_labels and allergens are deliberately left
alone — they are safety-bearing, were derived by the same function at import,
and silently churning them from a nutrition fix is exactly the kind of change
that should be its own reviewed pass.

Idempotent. A row that still cannot be derived keeps an existing `llm` estimate
rather than being wiped, so re-running costs nothing and never strips the corpus
of nutrition; a usable derivation still replaces an estimate, since computed
beats guessed.

Run from backend/ (DB must be up):
  ../.venv/bin/python -m scripts.rederive_nutrition --dry
  ../.venv/bin/python -m scripts.rederive_nutrition
  ../.venv/bin/python -m scripts.rederive_nutrition --stats   # writes nothing

Against production, in this order — the last two steps are the ones that get
forgotten, and skipping either leaves the fix invisible:

  1. Snapshot. Cheap, and the undo is one statement:
       CREATE TABLE recipes_nutrition_backup_<date> AS
         SELECT id, nutrition, nutrition_estimated FROM recipes;
  2. --stats, and keep the output. It is the only "before" you get.
  3. --dry, then apply. Stage it with --source if you want to inspect between
     batches (seed, generated, themealdb, archanas).
  4. scripts.estimate_nutrition_llm, which fills the rows this one rejected.
     Without it those recipes show no nutrition at all.
  5. Clear the cached recommendations, or users keep being served the old
     numbers. RANKING_VERSION does NOT cover this — the code did not change,
     only the data, so the cache keys are identical:
       redis-cli -u "$REDIS_URL" --scan --pattern 'rec:*' \
         | xargs -r redis-cli -u "$REDIS_URL" DEL
  6. --stats again and compare against step 2. p99 calories should fall; p50
     should barely move. A large p50 shift means the gram changes over-corrected
     and deflated the whole corpus, which is the failure mode to watch for.

Alembic runs inside the API container on boot (see backend/Dockerfile CMD), so
schema changes need no separate step — but this script does, because it rewrites
data rather than schema.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db import SessionLocal
from app.models import Ingredient, Recipe
from app.services.derivation import (
    classify_and_derive,
    load_props,
    measure_to_grams,
    nutrition_usable,
)


def _percentiles(values: list[float], points=(50, 90, 95, 99)) -> str:
    if not values:
        return "n=0"
    values = sorted(values)
    out = []
    for p in points:
        idx = min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))
        out.append(f"p{p}={values[idx]:.1f}")
    return "  ".join(out)


def _print_stats() -> int:
    """Per-serving distribution of the stored nutrition. Writes nothing.

    Lives here rather than in a query so the before and after of a re-derivation
    are produced by the same code and are actually comparable.
    """
    with SessionLocal() as session:
        rows = [r.nutrition or {} for r in session.execute(select(Recipe)).scalars()]
    have = [n for n in rows if n.get("calories")]
    print(f"n={len(have)} with nutrition, {len(rows) - len(have)} without")
    for key in ("calories", "protein_g", "fat_g", "carbs_g"):
        print(f"  {key:10} {_percentiles([n.get(key, 0.0) for n in have])}")
    over = {
        "cal>%g" % settings.NUTRI_MAX_CALORIES:
            sum(1 for n in have if n.get("calories", 0) > settings.NUTRI_MAX_CALORIES),
        "protein>%g" % settings.NUTRI_MAX_PROTEIN_G:
            sum(1 for n in have if n.get("protein_g", 0) > settings.NUTRI_MAX_PROTEIN_G),
        "fat>%g" % settings.NUTRI_MAX_FAT_G:
            sum(1 for n in have if n.get("fat_g", 0) > settings.NUTRI_MAX_FAT_G),
        "carbs>%g" % settings.NUTRI_MAX_CARBS_G:
            sum(1 for n in have if n.get("carbs_g", 0) > settings.NUTRI_MAX_CARBS_G),
    }
    print("  over ceilings: " + " | ".join(f"{k}: {v}" for k, v in over.items()))
    print(f"  unusable overall: {sum(1 for n in have if not nutrition_usable(n))}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="report only, no writes")
    ap.add_argument("--sample", type=int, default=5, help="before/after rows to print")
    ap.add_argument("--labels", action="store_true",
                    help="also rewrite diet_labels/allergens (safety-bearing; review the delta)")
    ap.add_argument("--source", help="only this source (seed, themealdb, archanas, generated)")
    ap.add_argument("--limit", type=int, help="stop after this many recipes")
    ap.add_argument("--stats", action="store_true",
                    help="print the per-serving distribution and exit, writing nothing")
    args = ap.parse_args()

    if args.stats:
        return _print_stats()

    changed = 0
    emptied = 0
    rejected = 0
    kept_llm = 0
    samples: list[str] = []
    label_delta: list[tuple] = []

    with SessionLocal() as session:
        props = load_props(session)
        names = {i.id: i.name for i in session.execute(select(Ingredient)).scalars()}
        query = select(Recipe).options(selectinload(Recipe.recipe_ingredients))
        if args.source:
            query = query.where(Recipe.source == args.source)
        if args.limit:
            query = query.limit(args.limit)
        recipes = session.execute(query).scalars().all()
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
            # An implausible sum is worse than no sum: ordering by a macro floats
            # exactly those rows to the top. Dropping it here rather than merely
            # counting it also gives the LLM backfill a queryable work queue
            # instead of a printed statistic.
            if after and not nutrition_usable(after):
                rejected += 1
                after = {}
            # A row we could not derive but previously estimated keeps its
            # estimate. Wiping it would discard paid-for work on every re-run and
            # silently strip the corpus of nutrition if this is run without the
            # backfill afterwards. A usable derivation still wins: computed beats
            # guessed whenever we have the choice.
            if not after and recipe.nutrition_source == "llm" and recipe.nutrition:
                kept_llm += 1
                continue
            source = "derived" if after else "none"
            if before == after and recipe.nutrition_source == source:
                continue

            if not after:
                emptied += 1
            if len(samples) < args.sample:
                samples.append(
                    f"  {recipe.title[:38]:40}\n"
                    f"     before {before}\n     after  {after}"
                )
            recipe.nutrition = after
            recipe.nutrition_estimated = bool(after)
            recipe.nutrition_source = source
            changed += 1

        if args.dry:
            session.rollback()
        else:
            session.commit()

    print(f"\nchanged {changed}{' (dry run)' if args.dry else ''}; "
          f"{emptied} now have no usable nutrition "
          f"({rejected} of those rejected as implausible, awaiting an estimate); "
          f"{kept_llm} kept an existing estimate")
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
