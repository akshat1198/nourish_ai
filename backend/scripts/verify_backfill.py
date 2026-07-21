"""Spot-verify: does the backfilled DB match a FRESH parse of the raw source?

For a spread sample of raw archana_dataset.csv rows, run the importer's own
normalize_row() with the current (fixed) vocab and compare the resulting canonical
ingredient set to what's stored in recipe_ingredients (which the backfill
produced). If they agree, the backfill == a fresh re-import for ingredient
mapping. Read-only.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Ingredient, Recipe, RecipeIngredient  # noqa: E402
from app.services.ingredients import normalize  # noqa: E402
from scripts.ingest.archanas import CSV, normalize_row  # noqa: E402
from scripts.ingest.pipeline import load_props  # noqa: E402

csv.field_size_limit(10**7)
STEP = int(sys.argv[1]) if len(sys.argv) > 1 else 25  # sample every STEP-th row


def main() -> None:
    props, matcher = load_props()
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    sample = rows[::STEP]

    with SessionLocal() as s:
        id_to_name = {i.id: i.name for i in s.execute(select(Ingredient)).scalars()}
        by_recipe: dict[int, set] = {}
        for rid, iid in s.execute(
            select(RecipeIngredient.recipe_id, RecipeIngredient.ingredient_id)
        ).all():
            by_recipe.setdefault(rid, set()).add(id_to_name.get(iid))
        db_by_title: dict[str, set] = {}
        for rec in s.execute(select(Recipe).where(Recipe.source == "archanas")).scalars():
            db_by_title[normalize(rec.title)] = by_recipe.get(rec.id, set())

    checked = exact = 0
    mismatches = []
    for row in sample:
        n = normalize_row(row, props, matcher)
        if not n:
            continue
        title_norm = normalize(n["fields"]["title"])
        if title_norm not in db_by_title:
            continue  # row not in DB (inter-row dup during original import)
        checked += 1
        fresh = {c for c, *_ in n["matched_items"]}
        stored = db_by_title[title_norm]
        if fresh == stored:
            exact += 1
        else:
            mismatches.append((n["fields"]["title"][:48], fresh - stored, stored - fresh))

    print(f"sampled every {STEP}th row → checked {checked} recipes present in DB")
    print(f"EXACT canonical-set match: {exact}/{checked} "
          f"({100 * exact / max(1, checked):.1f}%)")
    if mismatches:
        print(f"\n{len(mismatches)} differ — first 15 (fresh-only | db-only):")
        for title, fresh_only, db_only in mismatches[:15]:
            print(f"  • {title}")
            if fresh_only:
                print(f"      fresh has, db lacks: {sorted(fresh_only)}")
            if db_only:
                print(f"      db has, fresh lacks: {sorted(db_only)}")


if __name__ == "__main__":
    main()
