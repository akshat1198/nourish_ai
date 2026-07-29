"""Fill in nutrition for recipes the derivation could not compute.

Run AFTER `rederive_nutrition`, which is what marks a row `nutrition_source =
'none'`: either too few ingredients resolved to sum anything, or the sum landed
outside the per-serving plausibility ceilings. Those rows are the work queue, so
this script is resumable — re-running it picks up whatever is still 'none'.

Offline rather than lazy on first view, for a reason beyond cost: retrieval
filters and orders on `recipes.nutrition` in SQL while selecting candidates, so
a value computed after retrieval could only change what a card displays. It
could never surface a recipe the SQL filter had already dropped.

Nothing the model returns is trusted: `estimate_nutrition` range-checks it
against the same ceilings a derived value must clear and reconciles the macros
against the calorie total before this script ever sees it. A rejected estimate
leaves the row untouched at 'none'.

Step 4 of the rollout in scripts/rederive_nutrition.py — run that first, and do
not skip the cache flush that follows this.

Run from backend/ (DB must be up, ANTHROPIC_API_KEY must be set):
  ../.venv/bin/python -m scripts.estimate_nutrition_llm --dry --limit 20
  ../.venv/bin/python -m scripts.estimate_nutrition_llm

To undo a run, restore from the snapshot taken before the re-derivation:
  UPDATE recipes r SET nutrition = b.nutrition,
                       nutrition_estimated = b.nutrition_estimated
  FROM recipes_nutrition_backup_20260728 b WHERE b.id = r.id;
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.llm.client import is_enabled
from app.models import Recipe
from app.services.nutrition_estimate import as_nutrition, estimate_nutrition

COMMIT_EVERY = 25


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="report only, no writes")
    ap.add_argument("--limit", type=int, help="stop after this many recipes")
    ap.add_argument("--source", help="only this source (seed, themealdb, archanas, generated)")
    ap.add_argument("--sample", type=int, default=10, help="rows to print")
    args = ap.parse_args()

    if not is_enabled():
        print("LLM is not configured (ANTHROPIC_API_KEY unset) — nothing to do.")
        return 1

    accepted = rejected = 0
    # How often the model disagrees with the stored serving count. Diagnostic
    # only and never written: an unreliable `servings` is a large part of why
    # these rows are broken, and this says whether fixing it is worth a pass.
    disagreed = 0
    samples: list[str] = []

    with SessionLocal() as session:
        query = select(Recipe).where(Recipe.nutrition_source == "none")
        if args.source:
            query = query.where(Recipe.source == args.source)
        query = query.order_by(Recipe.id)
        if args.limit:
            query = query.limit(args.limit)
        recipes = session.execute(query).scalars().all()
        print(f"estimating nutrition for {len(recipes)} recipes...")

        for i, recipe in enumerate(recipes, 1):
            est = estimate_nutrition(recipe)
            if est is None:
                rejected += 1
                continue
            nutrition = as_nutrition(est)
            if est.serves and est.serves != recipe.servings:
                disagreed += 1
            if len(samples) < args.sample:
                samples.append(
                    f"  {recipe.title[:44]:46} {nutrition}"
                    f"  (claims {recipe.servings} servings, model read {est.serves or '?'})"
                )
            recipe.nutrition = nutrition
            recipe.nutrition_estimated = True
            recipe.nutrition_source = "llm"
            accepted += 1
            # Commit in batches so an interrupted run keeps the work it paid for.
            if not args.dry and i % COMMIT_EVERY == 0:
                session.commit()
                print(f"  ... {i}/{len(recipes)} ({accepted} accepted)")

        if args.dry:
            session.rollback()
        else:
            session.commit()

    print(f"\naccepted {accepted}{' (dry run)' if args.dry else ''}; "
          f"{rejected} left without nutrition (no estimate we could stand behind)")
    if accepted:
        print(f"the model read a different serving count on {disagreed}/{accepted} "
              f"of the ones it estimated")
    print("\nsample:")
    print("\n".join(samples))
    return 0


if __name__ == "__main__":
    sys.exit(main())
