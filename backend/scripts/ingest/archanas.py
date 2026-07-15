"""6.2d — import Archana's Kitchen (~6,871) into the corpus with provenance.

Reads the Translated* columns (English) + URL. Cuisine -> regional taxonomy,
Course -> meal_types, Diet -> seed labels + a non-veg override (catches Hindi
meat words the keyword backstop misses). Nutrition is derived from matched
ingredients where possible (nutrition_estimated=True), else hidden.

Licensing: Archana's is scraped — personal/family use, attribution kept, no
public-commercial redeploy of the content (the CSV stays gitignored).

Run from backend/ (DB must be up):
  ../.venv/bin/python -m scripts.ingest.archanas --dry            # report, no writes
  ../.venv/bin/python -m scripts.ingest.archanas --limit 500      # import a slice
  ../.venv/bin/python -m scripts.ingest.archanas                  # full import
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db import SessionLocal  # noqa: E402
from scripts.ingest.normalize import parse_ingredient_line  # noqa: E402
from scripts.ingest.pipeline import (  # noqa: E402
    Deduper,
    classify_and_derive,
    ensure_ingredients_in_db,
    load_props,
    measure_to_grams,
    upsert_recipe,
)
from scripts.ingest.taxonomy_maps import map_course, map_cuisine  # noqa: E402

csv.field_size_limit(10**7)
CSV = Path("/Applications/NourishAI/nourish_ai/archana_dataset.csv")
_NON_VEG_DIETS = {"non vegeterian", "high protein non vegetarian"}
_STAPLE_CATS = {"spice", "pantry", "sauce"}
_STAPLE_NAMES = {"salt", "water", "sugar", "olive oil", "oil", "black pepper"}
_ATTRIBUTION = "Archana's Kitchen (archanaskitchen.com)"
_LICENSE = "Archana's Kitchen — personal/family use, attribution required"


def _int(s: str, default: int) -> int:
    m = re.search(r"\d+", s or "")
    return int(m.group()) if m else default


def normalize_row(row: dict, props, matcher) -> dict | None:
    title = (row.get("TranslatedRecipeName") or "").strip()
    field = (row.get("TranslatedIngredients") or "").strip()
    url = (row.get("URL") or "").strip()
    if not title or not field:
        return None
    lines = [x for x in field.split(",") if x.strip()]
    if not lines:
        return None

    raw_names, display, matched_items, gram_items = [], [], [], []
    for ln in lines:
        p = parse_ingredient_line(ln)
        core = p.core
        if not core:
            continue
        raw_names.append(core)
        canon = matcher.match(core)
        disp = canon or core
        essential = not (
            canon and (props[canon]["category"] in _STAPLE_CATS or canon in _STAPLE_NAMES)
        )
        unit = p.unit
        display.append({"name": disp, "qty": float(p.qty) if p.qty else None,
                        "unit": unit, "essential": essential})
        if canon:
            g = measure_to_grams(props, canon, f"{p.qty or ''} {unit or ''}")
            gram_items.append((canon, g, essential))
            matched_items.append((canon, float(p.qty) if p.qty else None, unit, essential))

    diet_raw = (row.get("Diet") or "").replace("﻿", "").strip().lower()
    cuisine, region = map_cuisine(row.get("Cuisine", ""))
    servings = max(1, _int(row.get("Servings", ""), 4))
    derived = classify_and_derive(props, gram_items, raw_names, servings,
                                  force_non_veg=diet_raw in _NON_VEG_DIETS,
                                  title=title)
    instr = (row.get("TranslatedInstructions") or "").replace("\r\n", "\n")
    steps = [s.strip() for s in re.split(r"\n|(?<=[.!?])\s+", instr) if len(s.strip()) > 3] \
        or [instr.strip()]
    tags = [t for t in [cuisine, region, (row.get("Course") or "").strip().lower()] if t]
    matched_names = [n for n, *_ in gram_items]

    fields = {
        "title": title,
        "description": steps[0][:200] if steps else "",
        "ingredients": display,
        "steps": steps,
        "tags": list(dict.fromkeys(tags)),
        # Ingredient-grounded ONLY: the source Diet column is unreliable (it
        # mislabels some meat dishes "Vegetarian"), so it never asserts veg/vegan
        # here — it only strengthens safety via force_non_veg above.
        "diet_labels": derived["diet_labels"],
        "allergens": derived["allergens"],
        "cuisine": cuisine,
        "region": region,
        "meal_types": map_course(row.get("Course", "")),
        "time_minutes": _int(row.get("TotalTimeInMins", ""), 40) or 40,
        "servings": servings,
        "nutrition": derived["nutrition"],
        "nutrition_estimated": True,
        "search_text": " ".join([title] + matched_names + tags),
        "source": "archanas",
        "source_url": url or None,
        "image_url": None,   # not in the dataset
        "attribution": _ATTRIBUTION,
        "license_note": _LICENSE,
    }
    return {"fields": fields, "matched_items": matched_items,
            "match_frac": len(gram_items) / len(lines)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if not CSV.exists():
        sys.exit(f"CSV not found: {CSV}")

    props, matcher = load_props()
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    print(f"read {len(rows)} rows from {CSV.name}")

    normd = [n for r in rows if (n := normalize_row(r, props, matcher))]
    mean_match = sum(n["match_frac"] for n in normd) / max(1, len(normd))
    cuisine_hit = sum(1 for n in normd if n["fields"]["cuisine"])
    region_hit = sum(1 for n in normd if n["fields"]["region"])
    print(f"normalized {len(normd)}; mean ingredient match {100*mean_match:.0f}%; "
          f"cuisine {cuisine_hit} ({100*cuisine_hit/max(1,len(normd)):.0f}%), "
          f"region {region_hit} ({100*region_hit/max(1,len(normd)):.0f}%)")

    if args.dry:
        for n in normd[:3]:
            s = n["fields"]
            print(f"\n• {s['title'][:55]} | {s['cuisine']}/{s['region']} {s['meal_types']} "
                  f"diet={s['diet_labels']} allerg={s['allergens']} "
                  f"nutri={'yes' if s['nutrition'] else 'no'} url={bool(s['source_url'])}")
        print("\n(dry run — nothing written)")
        return

    created = dup = 0
    with SessionLocal() as session:
        name_to_id = ensure_ingredients_in_db(session)
        deduper = Deduper(session)
        for i, n in enumerate(normd):
            if args.limit and created >= args.limit:
                break
            status = upsert_recipe(session, name_to_id, n["fields"], n["matched_items"], deduper)
            created += status == "created"
            dup += status.startswith("dup")
            if created and created % 1000 == 0:
                session.flush()
                print(f"  …{created} created")
        session.commit()
    print(f"\nimported: {created} created, {dup} skipped (dup). "
          f"Run embed_recipes.py next (6.3) to embed the full corpus.")


if __name__ == "__main__":
    main()
