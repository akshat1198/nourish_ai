"""Re-derive cuisine/region for imported recipes the taxonomy couldn't place.

Both importers store cuisine=NULL when the source value has no taxonomy entry,
and a NULL cuisine is invisible to every cuisine filter (see cuisine_matches).
When the taxonomy grows, the already-imported rows keep their NULLs until this
runs — it re-reads each source's own cuisine field and re-applies the maps.

Rows whose source value is a genuine catch-all (Archana's "Continental" and
"Fusion", TheMealDB's blank area) stay NULL by design; there is no honest
cuisine to assign them.

Idempotent — re-running recomputes from the sources and only writes changes.

Run from backend/ (DB must be up):
  ../.venv/bin/python -m scripts.backfill_missing_cuisines --dry
  ../.venv/bin/python -m scripts.backfill_missing_cuisines
"""
from __future__ import annotations

import argparse
import csv
import string
import sys
import time
from collections import Counter
from pathlib import Path

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Recipe
from scripts.ingest.taxonomy_maps import map_cuisine, map_mealdb_area

MEALDB_SEARCH = "https://www.themealdb.com/api/json/v1/1/search.php?f="
ARCHANA_CSV = Path(__file__).resolve().parents[2] / "archana_dataset.csv"


def _mealdb_areas() -> dict[str, str]:
    """Lowercased meal title -> strArea, over the whole free a-z listing."""
    areas: dict[str, str] = {}
    with httpx.Client(timeout=30) as client:
        for letter in string.ascii_lowercase:
            payload = client.get(f"{MEALDB_SEARCH}{letter}").json() or {}
            for meal in payload.get("meals") or []:
                title = (meal.get("strMeal") or "").strip().lower()
                area = (meal.get("strArea") or "").strip()
                if title and area:
                    areas[title] = area
            time.sleep(0.1)  # be polite to the free endpoint
    return areas


def _archana_cuisines() -> dict[str, str]:
    """Lowercased recipe title -> raw Cuisine column."""
    if not ARCHANA_CSV.exists():
        return {}
    out: dict[str, str] = {}
    with ARCHANA_CSV.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            title = (row.get("TranslatedRecipeName") or "").strip().lower()
            raw = (row.get("Cuisine") or "").strip()
            if title and raw:
                out[title] = raw
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="report only, no writes")
    args = ap.parse_args()

    print("fetching TheMealDB areas...", flush=True)
    mealdb = _mealdb_areas()
    archana = _archana_cuisines()
    print(f"  themealdb titles: {len(mealdb)}   archana titles: {len(archana)}")

    applied: Counter[str] = Counter()
    unresolved: Counter[str] = Counter()

    with SessionLocal() as session:
        rows = session.execute(
            select(Recipe).where(Recipe.cuisine.is_(None))
        ).scalars().all()
        print(f"recipes with NULL cuisine: {len(rows)}")

        for recipe in rows:
            key = recipe.title.strip().lower()
            if recipe.source == "themealdb":
                raw = mealdb.get(key)
                cuisine, region = map_mealdb_area(raw) if raw else (None, None)
            elif recipe.source == "archanas":
                raw = archana.get(key)
                cuisine, region = map_cuisine(raw) if raw else (None, None)
            else:
                continue

            if cuisine is None:
                unresolved[(raw or "(no source value)").lower()] += 1
                continue
            recipe.cuisine = cuisine
            recipe.region = region
            applied[f"{cuisine}/{region}" if region else cuisine] += 1

        if args.dry:
            session.rollback()
        else:
            session.commit()

    print(f"\nresolved {sum(applied.values())} recipe(s){' (dry run)' if args.dry else ''}:")
    for label, n in applied.most_common():
        print(f"  {label:34} {n:5}")
    print(f"\nstill NULL ({sum(unresolved.values())}) — no honest cuisine to assign:")
    for label, n in unresolved.most_common(12):
        print(f"  {label:34} {n:5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
