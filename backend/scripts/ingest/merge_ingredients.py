"""6.2b — fold ingredients_enriched.json into ingredients.json (reviewable diff).

- alias decisions -> add the core (+ its aliases) to the target canonical's
  alias list.
- new decisions   -> append a canonical entry in the ingredients.json schema;
  if the name collides with an existing canonical, downgrade to an alias.
- skip decisions  -> ignored.

Idempotent (keyed by canonical name / normalized alias). Run from backend/:
  ../.venv/bin/python -m scripts.ingest.merge_ingredients [--dry]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.ingredients import normalize  # noqa: E402

SEED = Path(__file__).resolve().parents[2] / "seed_data"
VALID_CATEGORIES = {"protein", "grain", "starch", "vegetable", "herb", "fruit",
                    "dairy", "pantry", "sauce", "spice"}
# Allergen tokens must match the retrieval filter vocab exactly, so normalize
# the LLM's near-variants ("tree nuts"->nuts, "egg"->eggs) and drop anything off-vocab.
ALLOWED_ALLERGENS = {"gluten", "dairy", "nuts", "peanuts", "eggs", "soy",
                     "shellfish", "fish", "sesame"}
_ALLERGEN_REMAP = {"tree nuts": "nuts", "tree nut": "nuts", "treenuts": "nuts",
                   "egg": "eggs", "milk": "dairy", "wheat": "gluten", "peanut": "peanuts"}


def _clean_allergens(raw: list) -> list:
    out: list[str] = []
    for a in raw or []:
        t = _ALLERGEN_REMAP.get(str(a).strip().lower(), str(a).strip().lower())
        if t in ALLOWED_ALLERGENS and t not in out:
            out.append(t)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    ings = json.load(open(SEED / "ingredients.json"))
    enriched = json.load(open(SEED / "ingredients_enriched.json"))

    by_name = {i["name"].lower(): i for i in ings}
    # every string currently claimed by some canonical (name or alias)
    claimed = set()
    for i in ings:
        claimed.add(normalize(i["name"]))
        for a in i.get("aliases", []):
            claimed.add(normalize(a))

    added_new = added_alias = skipped = downgraded = 0

    def add_alias(target_name: str, alias: str) -> bool:
        norm = normalize(alias)
        if not norm or norm in claimed:
            return False
        tgt = by_name.get(target_name.lower())
        if not tgt:
            return False
        tgt.setdefault("aliases", []).append(alias.lower())
        claimed.add(norm)
        return True

    # Pass 1: create all new canonicals first, so aliases can target them.
    # Pass 2: attach aliases. (skip is a no-op.)
    for e in sorted(enriched, key=lambda x: {"new": 0, "alias": 1, "skip": 2}.get(x.get("decision"), 2)):
        d = e.get("decision")
        if d == "skip":
            skipped += 1
            continue
        if d == "alias":
            if add_alias(e.get("alias_of") or "", e["core"]):
                added_alias += 1
            continue
        if d == "new":
            name = (e.get("name") or e["core"]).strip().lower()
            cat = e.get("category")
            if cat not in VALID_CATEGORIES or not e.get("per_100g"):
                skipped += 1
                continue
            if normalize(name) in claimed:  # collides -> alias to whoever owns it
                if name in by_name and add_alias(name, e["core"]):
                    added_alias += 1
                else:
                    skipped += 1
                continue
            p = e["per_100g"]
            entry = {
                "name": name,
                "category": cat,
                "aliases": sorted({a.lower() for a in ([e["core"]] + (e.get("aliases") or []))
                                   if normalize(a) != normalize(name) and normalize(a) not in claimed}),
                "allergens": _clean_allergens(e.get("allergens")),
                "vegan": bool(e.get("vegan")),
                "vegetarian": bool(e.get("vegetarian")),
                "default_unit": e.get("default_unit") or "g",
                "grams_per_unit": e.get("grams_per_unit") or 1,
                "per_100g": {k: p[k] for k in ("calories", "protein_g", "carbs_g", "fat_g")},
            }
            ings.append(entry)
            by_name[name] = entry
            claimed.add(normalize(name))
            for a in entry["aliases"]:
                claimed.add(normalize(a))
            added_new += 1

    # Normalize allergen tokens across the WHOLE list (incl. the original seed
    # ingredients) to the frontend filter vocab — fixes a pre-existing "egg" vs
    # "eggs" mismatch that silently defeated the egg-allergen filter.
    for i in ings:
        i["allergens"] = _clean_allergens(i.get("allergens"))

    print(f"new canonicals: +{added_new}   aliases: +{added_alias}   "
          f"skipped: {skipped}   -> total ingredients: {len(ings)}")
    if args.dry:
        print("(dry run — not written)")
        return
    (SEED / "ingredients.json").write_text(json.dumps(ings, ensure_ascii=False, indent=1))
    print(f"wrote {SEED / 'ingredients.json'}")


if __name__ == "__main__":
    main()
