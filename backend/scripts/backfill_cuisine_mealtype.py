"""Backfill recipes.cuisine / region / meal_types for the seed corpus (Stage 5).

Cuisine + region are derived deterministically from the existing cuisine tags
(the seed already tags italian/thai/chinese/... on every recipe). meal_types are
derived from a keyword heuristic over title + tags — good enough for the 144-recipe
seed demo; the Stage-6 ingest pipeline classifies the real corpus with the LLM.

Idempotent: re-running recomputes from tags. Regional Indian (gujarati/punjabi/…)
is left NULL — the seed has no regional info; that's what Stage 6 adds.

Run:  python -m scripts.backfill_cuisine_mealtype          # writes + prints summary
      python -m scripts.backfill_cuisine_mealtype --dry    # print only, no writes
"""
from __future__ import annotations

import argparse
from collections import Counter

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Recipe

# Specific tags first so "chinese" beats generic "asian".
CUISINE_TAG_MAP: dict[str, tuple[str, str | None]] = {
    "chinese": ("asian", "chinese"),
    "japanese": ("asian", "japanese"),
    "thai": ("asian", "thai"),
    "asian": ("asian", None),
    "italian": ("italian", None),
    "tex-mex": ("mexican", None),
    "mexican": ("mexican", None),
    "mediterranean": ("mediterranean", None),
    "middle-eastern": ("middle-eastern", None),
    "american": ("american", None),
    "indian": ("indian", None),
    # deliberately unmapped (stay NULL): fusion, french
}
_PRIORITY = list(CUISINE_TAG_MAP.keys())

_DESSERT = {"dessert", "cake", "cookie", "pie", "brownie", "pudding", "tart", "sweet"}
_BREAKFAST = {
    "pancake", "oat", "oatmeal", "toast", "smoothie", "granola", "omelet",
    "omelette", "frittata", "waffle", "shakshuka", "porridge", "muffin", "scramble",
}
_SNACK = {"dip", "chips", "hummus", "snack", "bites", "nachos", "popcorn"}


def _cuisine_for(tags: list[str]) -> tuple[str | None, str | None]:
    tagset = {t.lower() for t in tags or []}
    for tag in _PRIORITY:
        if tag in tagset:
            return CUISINE_TAG_MAP[tag]
    return None, None


def _meal_types_for(title: str, tags: list[str]) -> list[str]:
    hay = title.lower() + " " + " ".join(tags or []).lower()
    words = set(hay.replace("-", " ").split())
    if words & _DESSERT:
        return ["dessert"]
    if words & _BREAKFAST:
        return ["breakfast"]
    if words & _SNACK:
        return ["snack"]
    return ["lunch", "dinner"]  # default: a savory main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="print only, do not write")
    args = ap.parse_args()

    cuis, meals, unmapped = Counter(), Counter(), []
    with SessionLocal() as session:
        recipes = list(session.execute(select(Recipe)).scalars())
        for r in recipes:
            cuisine, region = _cuisine_for(r.tags)
            meal_types = _meal_types_for(r.title, r.tags)
            cuis[cuisine or "(none)"] += 1
            for m in meal_types:
                meals[m] += 1
            if cuisine is None:
                unmapped.append(r.title)
            if not args.dry:
                r.cuisine, r.region, r.meal_types = cuisine, region, meal_types
        if not args.dry:
            session.commit()

    print(f"{'DRY RUN — ' if args.dry else ''}{len(recipes)} recipes")
    print("cuisine:", dict(cuis.most_common()))
    print("meal_types:", dict(meals.most_common()))
    if unmapped:
        print(f"unmapped cuisine ({len(unmapped)}):", ", ".join(unmapped[:10]))


if __name__ == "__main__":
    main()
