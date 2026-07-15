"""Shared ingestion engine used by both importers (themealdb, archanas).

Responsibilities:
- ensure_ingredients_in_db: upsert the ingredients.json vocab (275) into the DB
  so recipe_ingredients can reference real ids (existing ids untouched).
- classify_and_derive: allergens / diet_labels / nutrition from MATCHED canonical
  ingredient properties, PLUS a keyword safety backstop over the raw ingredient
  text — so an unmatched meat/fish/egg line can't let a dish be mislabelled
  vegetarian/vegan (partial-match safety). Nutrition is coarse -> estimated=True.
- upsert_recipe: create Recipe + RecipeIngredient, skipping title/source dups.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from app.models import Ingredient, Recipe, RecipeIngredient
from app.services.ingredients import normalize
from scripts.ingest.normalize import CanonicalMatcher

SEED = Path(__file__).resolve().parents[2] / "seed_data"

# --- keyword safety backstop (high-confidence tokens only) ------------------
_NON_VEG_KW = {
    "chicken", "beef", "pork", "lamb", "mutton", "veal", "bacon", "ham",
    "sausage", "salami", "pepperoni", "meat", "mince", "steak", "gelatin",
    "gelatine", "prawn", "shrimp", "crab", "lobster", "fish", "salmon", "tuna",
    "cod", "anchovy", "anchovies", "oyster", "mussel", "clam", "squid",
    "octopus", "duck", "turkey", "goat", "keema", "kheema",
}
_FISH_KW = {"fish", "salmon", "tuna", "cod", "anchovy", "anchovies", "sardine"}
_SHELLFISH_KW = {"prawn", "shrimp", "crab", "lobster", "oyster", "mussel", "clam", "squid"}
_NON_VEGAN_KW = {"egg", "eggs", "milk", "cheese", "butter", "cream", "ghee",
                 "paneer", "yogurt", "yoghurt", "curd", "khoya", "honey", "mayonnaise"}
_ALLERGEN_KW = {
    "nuts": {"almond", "cashew", "walnut", "pistachio", "hazelnut", "pecan", "badam"},
    "peanuts": {"peanut", "groundnut"},
    "sesame": {"sesame", "tahini", "til"},
    "eggs": {"egg", "eggs"},
    "dairy": {"milk", "cheese", "butter", "cream", "ghee", "paneer", "yogurt", "yoghurt", "curd"},
}
_MEAT_CATEGORIES = {"beef", "chicken", "pork", "lamb", "goat", "seafood"}


def _kw_hit(text: str, kws: set[str]) -> bool:
    # Singularize each word so plurals ("shrimps", "prawns", "eggs") still match
    # the singular keyword sets — a safety-critical detail for allergen/veg flags.
    words = set(re.findall(r"[a-z]+", text.lower()))
    words |= {w[:-1] for w in words if w.endswith("s") and not w.endswith("ss")}
    return bool(words & kws)


@dataclass
class Vocab:
    props: dict            # canonical name -> properties dict
    matcher: CanonicalMatcher
    name_to_id: dict       # canonical name -> DB ingredient id


def load_props() -> tuple[dict, CanonicalMatcher]:
    ings = json.loads((SEED / "ingredients.json").read_text())
    props = {i["name"]: i for i in ings}
    return props, CanonicalMatcher(ings)


def ensure_ingredients_in_db(session) -> dict:
    """Upsert ingredients.json into the ingredients table; return name->id.

    Adds missing canonicals and merges new aliases into existing rows. Existing
    ids are never changed, so the 144 seed recipes stay intact.
    """
    ings = json.loads((SEED / "ingredients.json").read_text())
    existing = {i.name.lower(): i for i in session.execute(select(Ingredient)).scalars()}
    name_to_id: dict[str, int] = {}
    added = 0
    for spec in ings:
        row = existing.get(spec["name"].lower())
        if row is None:
            row = Ingredient(name=spec["name"], category=spec["category"],
                             aliases=list(spec.get("aliases", [])))
            session.add(row)
            session.flush()
            existing[spec["name"].lower()] = row
            added += 1
        else:
            merged = list(dict.fromkeys((row.aliases or []) + list(spec.get("aliases", []))))
            if merged != (row.aliases or []):
                row.aliases = merged
        name_to_id[spec["name"]] = row.id
    session.flush()
    if added:
        print(f"  ensured ingredients: +{added} new canonicals in DB")
    return name_to_id


def classify_and_derive(
    props: dict,
    matched_items: list[tuple],   # (canonical_name, grams, essential)
    raw_names: list[str],
    servings: int,
    category: Optional[str] = None,
) -> dict:
    raw_text = " ".join(raw_names)
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

    # --- veg / vegan: matched AND, then keyword + category backstop ---
    vegetarian = all(props[n].get("vegetarian", False) for n, _g, _e in matched_items) \
        if matched_items else False
    vegan = all(props[n].get("vegan", False) for n, _g, _e in matched_items) \
        if matched_items else False
    if _kw_hit(raw_text, _NON_VEG_KW) or (category or "").lower() in _MEAT_CATEGORIES:
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


def measure_to_grams(props: dict, name: str, measure: str) -> float:
    """Best-effort grams for one ingredient line (nutrition is estimated)."""
    m = (measure or "").lower()
    num = re.search(r"(\d+(?:\.\d+)?)", m)
    qty = float(num.group(1)) if num else 1.0
    if re.search(r"\bkg\b|kilogram", m):
        return qty * 1000
    if re.search(r"\bg\b|gram", m):
        return qty
    if re.search(r"\bml\b|litre|liter|\bl\b|cup", m):
        return qty * (240 if "cup" in m else 1)   # ~1g/ml
    if re.search(r"tbsp|tablespoon", m):
        return qty * 15
    if re.search(r"tsp|teaspoon", m):
        return qty * 5
    gpu = props.get(name, {}).get("grams_per_unit") or 50
    return qty * gpu


def title_exists(session, title: str) -> bool:
    norm = normalize(title)
    rows = session.execute(select(Recipe.title)).scalars()
    return any(normalize(t) == norm for t in rows)


def upsert_recipe(session, name_to_id: dict, fields: dict, matched_items: list[tuple]) -> str:
    """matched_items: (canonical_name, qty, unit, essential). Returns status."""
    exists = session.execute(
        select(Recipe.id).where(Recipe.source == fields["source"],
                                Recipe.source_url == fields.get("source_url"))
    ).first()
    if exists and fields.get("source_url"):
        return "dup_source"
    if title_exists(session, fields["title"]):
        return "dup_title"
    recipe = Recipe(**{k: v for k, v in fields.items() if k != "_ingredient_lines"})
    session.add(recipe)
    session.flush()
    seen = set()
    for cname, qty, unit, essential in matched_items:
        iid = name_to_id.get(cname)
        if iid is None or iid in seen:
            continue
        seen.add(iid)
        session.add(RecipeIngredient(recipe_id=recipe.id, ingredient_id=iid,
                                     qty=qty, unit=unit, essential=essential))
    return "created"
