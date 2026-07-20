"""Diet / allergen / nutrition derivation from canonical ingredient properties.

Extracted from the ingestion pipeline (Stage 7.3a) so the modify endpoint and
the importers share ONE implementation — a swap must re-validate diet/allergen
exactly the way ingestion first derived them, or the two would drift.

Lives in `app/` (not `scripts/`) and reads `seed_data/ingredients.json`
directly, because the canonical properties (vegetarian/vegan/allergens/per_100g)
live in that file, not the DB. The backend image must therefore ship
`seed_data/` (see Dockerfile).
"""
from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import Optional

from app.core.allergens import ALLERGEN_SET, clean_allergens

SEED = Path(__file__).resolve().parents[2] / "seed_data"

# --- keyword safety backstop (high-confidence tokens only) ------------------
_NON_VEG_KW = {
    "chicken", "beef", "pork", "lamb", "mutton", "veal", "bacon", "ham",
    "sausage", "salami", "pepperoni", "meat", "mince", "steak", "gelatin",
    "gelatine", "prawn", "shrimp", "crab", "lobster", "fish", "salmon", "tuna",
    "cod", "anchovy", "anchovies", "oyster", "mussel", "clam", "squid",
    "octopus", "duck", "turkey", "goat", "keema", "kheema",
    # Indian-language food words that survive into the (English) titles.
    "murgh", "murg", "gosht", "ghosht", "macchi", "machli", "machhi", "meen",
    "jhinga", "chingri", "mutton",
}
_FISH_KW = {"fish", "salmon", "tuna", "cod", "anchovy", "anchovies", "sardine",
            "macchi", "machli", "machhi", "meen"}
_SHELLFISH_KW = {"prawn", "shrimp", "crab", "lobster", "oyster", "mussel", "clam",
                 "squid", "jhinga", "chingri"}
_NON_VEGAN_KW = {"egg", "eggs", "milk", "cheese", "butter", "cream", "ghee",
                 "paneer", "yogurt", "yoghurt", "curd", "khoya", "honey", "mayonnaise"}
_ALLERGEN_KW = {
    "nuts": {"almond", "cashew", "walnut", "pistachio", "hazelnut", "pecan", "badam"},
    "peanuts": {"peanut", "groundnut"},
    "sesame": {"sesame", "tahini", "til"},
    "eggs": {"egg", "eggs"},
    "dairy": {"milk", "cheese", "butter", "cream", "ghee", "paneer", "yogurt", "yoghurt", "curd"},
}
# The keyword map's target tokens must be real allergen labels (single source of truth).
assert set(_ALLERGEN_KW) <= ALLERGEN_SET, f"off-vocab allergen keys: {set(_ALLERGEN_KW) - ALLERGEN_SET}"
_MEAT_CATEGORIES = {"beef", "chicken", "pork", "lamb", "goat", "seafood"}


@functools.lru_cache(maxsize=1)
def load_props() -> dict:
    """Canonical ingredient name -> properties, from seed_data/ingredients.json.

    Cached (the file is immutable at runtime). Used by the modify endpoint to
    re-derive diet/allergen on a post-swap ingredient set.
    """
    ings = json.loads((SEED / "ingredients.json").read_text())
    return {i["name"]: i for i in ings}


def _kw_hit(text: str, kws: set[str]) -> bool:
    # Singularize each word so plurals ("shrimps", "prawns", "eggs") still match
    # the singular keyword sets — a safety-critical detail for allergen/veg flags.
    words = set(re.findall(r"[a-z]+", text.lower()))
    words |= {w[:-1] for w in words if w.endswith("s") and not w.endswith("ss")}
    return bool(words & kws)


def classify_and_derive(
    props: dict,
    matched_items: list[tuple],   # (canonical_name, grams, essential)
    raw_names: list[str],
    servings: int,
    category: Optional[str] = None,
    force_non_veg: bool = False,   # source Diet column says non-veg (e.g. Hindi meat word)
    title: str = "",               # scanned too: catches "Chicken …" when the ingredient is unmatched
) -> dict:
    raw_text = " ".join(raw_names) + " " + title
    # --- allergens: matched props ∪ keyword backstop ---
    allergens: set[str] = set()
    for name, _g, _e in matched_items:
        allergens.update(props[name].get("allergens", []))
    for tok, kws in _ALLERGEN_KW.items():
        if _kw_hit(raw_text, kws):
            allergens.add(tok)
    if _kw_hit(raw_text, _FISH_KW):
        allergens.add("fish")
    if _kw_hit(raw_text, _SHELLFISH_KW):
        allergens.add("shellfish")
    allergens = set(clean_allergens(allergens))   # canonicalize to the shared vocab

    # --- veg / vegan: matched AND, then keyword + category backstop ---
    vegetarian = all(props[n].get("vegetarian", False) for n, _g, _e in matched_items) \
        if matched_items else False
    vegan = all(props[n].get("vegan", False) for n, _g, _e in matched_items) \
        if matched_items else False
    if force_non_veg or _kw_hit(raw_text, _NON_VEG_KW) \
            or (category or "").lower() in _MEAT_CATEGORIES:
        vegetarian = vegan = False
    if _kw_hit(raw_text, _NON_VEGAN_KW):
        vegan = False

    # --- nutrition: sum matched grams * per_100g/100, per serving. Coarse. ---
    total = dict(calories=0.0, protein_g=0.0, carbs_g=0.0, fat_g=0.0)
    for name, g, _e in matched_items:
        per = props[name].get("per_100g", {})
        for k in total:
            total[k] += g * per.get(k, 0) / 100
    servings = max(1, servings)
    nutrition = {k: round(v / servings, 1) for k, v in total.items()}
    # If we matched too little to trust it, hide nutrition rather than mislead.
    if len(matched_items) < 2 or total["calories"] <= 0:
        nutrition = {}

    labels: list[str] = []
    if vegan:
        labels.append("vegan")
    if vegetarian:
        labels.append("vegetarian")
    if "gluten" not in allergens:
        labels.append("gluten_free")
    if "dairy" not in allergens:
        labels.append("dairy_free")
    if "nuts" not in allergens:
        labels.append("nut_free")

    return {"allergens": sorted(allergens), "diet_labels": labels, "nutrition": nutrition}
