"""6.2c — import TheMealDB (free, open) into the corpus with provenance.

Fetches every meal (search.php?f=a..z on the free key "1"), normalizes via the
shared pipeline, and loads with source='themealdb'. Ingredient names + measures
come as separate fields (strIngredientN / strMeasureN), so parsing is clean.

Run from backend/ (DB must be up):
  ../.venv/bin/python -m scripts.ingest.themealdb --dry           # fetch + report, no writes
  ../.venv/bin/python -m scripts.ingest.themealdb                 # import
"""
from __future__ import annotations

import argparse
import string
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db import SessionLocal  # noqa: E402
from scripts.ingest.normalize import parse_ingredient_line  # noqa: E402
from scripts.ingest.pipeline import (  # noqa: E402
    classify_and_derive,
    ensure_ingredients_in_db,
    load_props,
    measure_to_grams,
    upsert_recipe,
)
from scripts.ingest.taxonomy_maps import map_mealdb_area, map_mealdb_category  # noqa: E402

API = "https://www.themealdb.com/api/json/v1/1/search.php?f="
DEFAULT_TIME, DEFAULT_SERVINGS = 40, 4
# Staple categories/names default to non-essential (don't gate pantry coverage).
_STAPLE_CATS = {"spice", "pantry", "sauce"}
_STAPLE_NAMES = {"salt", "water", "sugar", "olive oil", "oil", "black pepper"}


def fetch_all(delay: float = 0.2) -> list[dict]:
    meals: dict[str, dict] = {}
    with httpx.Client(timeout=20) as client:
        for ch in string.ascii_lowercase:
            try:
                data = client.get(API + ch).json()
            except Exception as e:
                print(f"  fetch '{ch}' failed: {e}")
                continue
            for m in data.get("meals") or []:
                meals[m["idMeal"]] = m
            time.sleep(delay)
    return list(meals.values())


def _lines(meal: dict) -> list[tuple[str, str]]:
    """(ingredient_name, measure) pairs, non-empty."""
    out = []
    for i in range(1, 21):
        name = (meal.get(f"strIngredient{i}") or "").strip()
        meas = (meal.get(f"strMeasure{i}") or "").strip()
        if name:
            out.append((name, meas))
    return out


def normalize_meal(meal: dict, props, matcher) -> dict | None:
    lines = _lines(meal)
    if not lines:
        return None
    raw_names = [n for n, _ in lines]
    display, matched_items, gram_items = [], [], []
    for name, meas in lines:
        core = parse_ingredient_line(name).core or name.lower()
        canon = matcher.match(core)
        disp_name = canon or name.lower()
        essential = not (
            canon and (props[canon]["category"] in _STAPLE_CATS or canon in _STAPLE_NAMES)
        )
        display.append({"name": disp_name, "qty": None, "unit": meas or None,
                        "essential": essential})
        if canon:
            g = measure_to_grams(props, canon, meas)
            gram_items.append((canon, g, essential))
            matched_items.append((canon, None, meas or None, essential))

    area = meal.get("strArea")
    cuisine, region = map_mealdb_area(area)
    derived = classify_and_derive(props, gram_items, raw_names, DEFAULT_SERVINGS,
                                  category=meal.get("strCategory"))
    instr = (meal.get("strInstructions") or "").replace("\r\n", "\n")
    steps = [s.strip() for s in instr.split("\n") if s.strip()] or [instr.strip()]
    tags = [t.strip().lower() for t in (meal.get("strTags") or "").split(",") if t.strip()]
    if meal.get("strCategory"):
        tags.append(meal["strCategory"].lower())
    matched_names = [n for n, *_ in gram_items]

    fields = {
        "title": meal["strMeal"].strip(),
        "description": steps[0][:200] if steps else "",
        "ingredients": display,
        "steps": steps,
        "tags": list(dict.fromkeys(tags)),
        "diet_labels": derived["diet_labels"],
        "allergens": derived["allergens"],
        "cuisine": cuisine,
        "region": region,
        "meal_types": map_mealdb_category(meal.get("strCategory")),
        "time_minutes": DEFAULT_TIME,
        "servings": DEFAULT_SERVINGS,
        "nutrition": derived["nutrition"],
        "nutrition_estimated": True,
        "search_text": " ".join([meal["strMeal"]] + matched_names + tags),
        "source": "themealdb",
        "source_url": (meal.get("strSource") or "").strip()
                      or f"https://www.themealdb.com/meal/{meal['idMeal']}",
        "image_url": meal.get("strMealThumb"),
        "attribution": "TheMealDB (themealdb.com)",
        "license_note": "TheMealDB — free/open recipe data",
    }
    return {"fields": fields, "matched_items": matched_items,
            "match_frac": len(gram_items) / len(lines)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="cap imported recipes (0=all)")
    args = ap.parse_args()

    props, matcher = load_props()
    print("fetching TheMealDB (a-z)…")
    meals = fetch_all()
    print(f"fetched {len(meals)} unique meals")

    normd = [n for m in meals if (n := normalize_meal(m, props, matcher))]
    mean_match = sum(n["match_frac"] for n in normd) / max(1, len(normd))
    cuisine_hit = sum(1 for n in normd if n["fields"]["cuisine"])
    print(f"normalized {len(normd)}; mean ingredient match {100*mean_match:.0f}%; "
          f"cuisine-mapped {cuisine_hit} ({100*cuisine_hit/max(1,len(normd)):.0f}%)")

    if args.dry:
        s = normd[0]["fields"]
        print(f"\nsample: {s['title']} | cuisine={s['cuisine']}/{s['region']} "
              f"meals={s['meal_types']} diet={s['diet_labels']} allergens={s['allergens']}")
        print(f"  ingredients: {len(s['ingredients'])}, nutrition={s['nutrition']}, url={s['source_url']}")
        print("(dry run — nothing written)")
        return

    created = dup = 0
    with SessionLocal() as session:
        name_to_id = ensure_ingredients_in_db(session)
        for n in normd:
            if args.limit and created >= args.limit:
                break
            status = upsert_recipe(session, name_to_id, n["fields"], n["matched_items"])
            created += status == "created"
            dup += status.startswith("dup")
        session.commit()
    print(f"\nimported: {created} created, {dup} skipped (dup). "
          f"embeddings NOT set — run embed_recipes.py after all imports.")


if __name__ == "__main__":
    main()
