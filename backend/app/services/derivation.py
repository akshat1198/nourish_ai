"""Diet / allergen / nutrition derivation from canonical ingredient properties.

Extracted from the ingestion pipeline so the modify endpoint and
the importers share ONE implementation — a swap must re-validate diet/allergen
exactly the way ingestion first derived them, or the two would drift.

Canonical properties (vegetarian/vegan/allergens/per_100g/gram weights) live on
the `ingredients` table, so a vocabulary entry added at runtime is immediately
usable. `seed_data/ingredients.json` remains the bootstrap for a fresh install
and the fallback when there is no session, so the backend image must still ship
`seed_data/` (see Dockerfile).
"""
from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import Optional

from sqlalchemy import select as sa_select

from app.core.allergens import ALLERGEN_SET, clean_allergens
from app.core.config import settings

SEED = Path(__file__).resolve().parents[2] / "seed_data"

# Largest bare quantity still read as a piece/cup count rather than grams.
# Real recipes stay well under it (30 curry leaves, 24 shrimp); source rows that
# dropped their "g" run far above it.
PIECE_COUNT_MAX = 40
# A kg figure above this is a source that wrote "kg" but meant grams.
KG_AS_GRAMS_ABOVE = 20
# Grams for a line carrying neither a quantity nor a unit. Ingestion strips the
# source qualifier ("Salt - to taste" loses everything after the dash), so its
# absence is the only signal left that the amount is a trace. Reading it as one
# whole piece instead put 6 g of salt and 15 g of oil into 9,124 of the corpus's
# 75,899 ingredient rows — the pantry category alone contributed ~205,000 kcal.
# Spices and herbs dominate by count; pantry items dominate by calories.
_TRACE_GRAMS = {"spice": 1.0, "herb": 1.0, "pantry": 5.0, "sauce": 5.0}
_TRACE_DEFAULT_GRAMS = 5.0
# Weight of one bare unit when the ingredient records no piece weight. Reached
# only by vocabulary added at runtime; every seeded row carries grams_per_piece.
DEFAULT_PIECE_GRAMS = 30

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
                 "paneer", "yogurt", "yoghurt", "curd", "khoya", "honey", "mayonnaise",
                 "buttermilk", "condensed milk"}
_ALLERGEN_KW = {
    "nuts": {"almond", "cashew", "walnut", "pistachio", "hazelnut", "pecan", "badam"},
    "peanuts": {"peanut", "groundnut"},
    "sesame": {"sesame", "tahini", "til"},
    "eggs": {"egg", "eggs"},
    "dairy": {"milk", "cheese", "butter", "cream", "ghee", "paneer", "yogurt", "yoghurt",
              "curd", "buttermilk", "khoya"},
}
# The keyword map's target tokens must be real allergen labels (single source of truth).
assert set(_ALLERGEN_KW) <= ALLERGEN_SET, f"off-vocab allergen keys: {set(_ALLERGEN_KW) - ALLERGEN_SET}"
_MEAT_CATEGORIES = {"beef", "chicken", "pork", "lamb", "goat", "seafood"}


def load_props(session=None) -> dict:
    """Canonical ingredient name -> properties.

    Reads the `ingredients` table when given a session, so an ingredient added
    at runtime is usable immediately. Without one it falls back to the seed
    file, which is the bootstrap for a fresh install and the only source
    available to tooling that runs before the DB exists.

    Deliberately uncached: the vocabulary grows at runtime now, and an
    lru_cache here would serve a snapshot taken before the newest ingredient
    was inserted — silently giving it no nutrition and no vegan flag.
    """
    if session is None:
        return _seed_props()
    from app.models import Ingredient  # local: avoids a models <-> services cycle

    props: dict[str, dict] = {}
    for ing in session.execute(sa_select(Ingredient)).scalars():
        props[ing.name] = {
            "name": ing.name,
            "category": ing.category,
            "aliases": ing.aliases or [],
            "vegetarian": bool(ing.vegetarian),
            "vegan": bool(ing.vegan),
            "allergens": ing.allergens or [],
            "per_100g": ing.per_100g or {},
            "default_unit": ing.default_unit,
            "grams_per_unit": float(ing.grams_per_unit) if ing.grams_per_unit else None,
            "grams_per_piece": float(ing.grams_per_piece) if ing.grams_per_piece else None,
            "grams_per_cup": float(ing.grams_per_cup) if ing.grams_per_cup else None,
        }
    return props


@functools.lru_cache(maxsize=1)
def _seed_props() -> dict:
    """Bootstrap properties straight from the immutable seed file."""
    ings = json.loads((SEED / "ingredients.json").read_text())
    return {i["name"]: i for i in ings}


def ingredient_columns(spec: dict) -> dict:
    """Seed-file entry -> Ingredient column values.

    One mapping shared by every writer (seeder, importer, and anything that
    adds vocabulary later). Creating a row without these leaves the properties
    NULL, which reads as "not vegan, no nutrition" rather than as missing data.
    """
    return {
        "name": spec["name"],
        "category": spec["category"],
        "aliases": list(spec.get("aliases", [])),
        "vegetarian": spec.get("vegetarian"),
        "vegan": spec.get("vegan"),
        "allergens": list(spec.get("allergens", [])),
        "per_100g": spec.get("per_100g") or {},
        "default_unit": spec.get("default_unit"),
        "grams_per_unit": spec.get("grams_per_unit"),
        "grams_per_piece": spec.get("grams_per_piece"),
        "grams_per_cup": spec.get("grams_per_cup"),
    }


def _parse_qty(m: str) -> Optional[float]:
    """Leading quantity, including vulgar fractions. None when there is no number.

    Sources write "1/2 lb" and "1 1/2 cups" freely; reading only the first digit
    turned every half into a whole and doubled those ingredients.

    Returns None rather than 1.0 for a measure with no digits at all. Defaulting
    to 1 was indistinguishable from a genuine "1", so a quantity-less line was
    silently priced as one whole piece of the ingredient; callers decide what an
    absent quantity means for the unit they matched.
    """
    mixed = re.search(r"(\d+)\s+(\d+)\s*/\s*(\d+)", m)
    if mixed:
        whole, num, den = (int(g) for g in mixed.groups())
        return whole + (num / den if den else 0)
    frac = re.search(r"(\d+)\s*/\s*(\d+)", m)
    if frac:
        num, den = (int(g) for g in frac.groups())
        return num / den if den else 1.0
    plain = re.search(r"(\d+(?:\.\d+)?)", m)
    return float(plain.group(1)) if plain else None


def measure_to_grams(props: dict, name: str, measure: str) -> float:
    """Best-effort grams for one ingredient line (nutrition is estimated)."""
    m = (measure or "").lower()
    raw_qty = _parse_qty(m)
    # A named unit with no number means one of it ("a tablespoon of oil"); an
    # absent quantity only changes the reading on the bare-number path below.
    qty = 1.0 if raw_qty is None else raw_qty
    entry = props.get(name, {})
    if re.search(r"\bkg\b|kilogram", m):
        # Sources write "750 kg" meaning 750 g. No home recipe uses tens of
        # kilos, so treat an implausible kg figure as the grams it must be.
        return qty if qty > KG_AS_GRAMS_ABOVE else qty * 1000
    # Imperial weights: TheMealDB uses them throughout, and unhandled they fell
    # through to the piece path — "8 oz" chicken became 8 breasts.
    if re.search(r"\blbs?\b|pound", m):
        return qty * 453.6
    if re.search(r"\boz\b|ounce", m):
        return qty * 28.35
    if re.search(r"pinch|dash|to taste|as needed|garnish|handful|sprinkle|drizzle", m):
        return 0.5
    # "\bg\b" cannot match "25g" — there is no word boundary between a digit and
    # the g that follows it — so gram weights written without a space fell all
    # the way through to the piece path (25 g of butter became 25 sticks).
    if re.search(r"\d\s*g\b|\bgram", m):
        return qty
    if "cup" in m:
        # A cup is a volume; only liquids weigh ~240 g. Prefer the ingredient's
        # own cup weight (rice ~185 g, flour ~120 g) when we have one. This is
        # NOT grams_per_piece: for anything counted individually the two differ
        # by orders of magnitude (a peanut is 0.5 g, a cup of them is 146 g).
        return qty * (entry.get("grams_per_cup") or entry.get("grams_per_piece") or 240)
    if re.search(r"\bml\b", m):
        return qty * 1  # ~1 g/ml
    # Litres were lumped in with millilitres and returned grams 1:1, reading
    # "2 litre" as 2 g. Latent today (no litre rows in the corpus) but wrong.
    if re.search(r"litre|liter|\bl\b", m):
        return qty * 1000
    if re.search(r"tbsp|tablespoon", m):
        return qty * 15
    if re.search(r"tsp|teaspoon", m):
        return qty * 5
    # No recognizable unit: the quantity counts bare units of this ingredient
    # ("3 chicken breast"). grams_per_unit is grams-per-default_unit and is 1
    # for everything stored in grams, so using it here shrank whole cuts to a
    # few grams — grams_per_piece is what one bare unit actually weighs.
    #
    # Above PIECE_COUNT_MAX the number is a gram weight whose unit went missing
    # in the source, not a piece count: no recipe calls for 500 chicken breasts,
    # and multiplying by the piece weight there produced a 39,696 kcal fritter.
    #
    # No quantity either: the line named an ingredient and nothing else, which
    # in this corpus means "to taste". Scale the trace by category — a bare spice
    # is a pinch, a bare oil or sugar is a spoonful and carries real calories.
    if raw_qty is None:
        return _TRACE_GRAMS.get(entry.get("category") or "", _TRACE_DEFAULT_GRAMS)
    if qty > PIECE_COUNT_MAX:
        return qty
    # `or` would treat a recorded 0 as missing; only an absent weight falls back.
    per_piece = entry.get("grams_per_piece")
    if per_piece is None:
        per_piece = entry.get("grams_per_unit")
    if per_piece is None:
        per_piece = DEFAULT_PIECE_GRAMS
    return qty * per_piece


# Per-serving plausibility bounds as (json key, floor setting, ceiling setting).
# Attribute names rather than values so the bounds resolve at call time: a test
# that overrides a ceiling gets the override, and the SQL mirror in
# retrieval.soft_clauses builds from this same table so the two cannot drift.
_PLAUSIBLE: tuple[tuple[str, Optional[str], str], ...] = (
    ("calories", "NUTRI_MIN_CALORIES", "NUTRI_MAX_CALORIES"),
    ("protein_g", None, "NUTRI_MAX_PROTEIN_G"),
    ("fat_g", None, "NUTRI_MAX_FAT_G"),
    ("carbs_g", None, "NUTRI_MAX_CARBS_G"),
)


def plausible_bounds() -> list[tuple[str, float, float]]:
    """(json key, floor, ceiling) for each macro, resolved from settings."""
    return [
        (key, getattr(settings, lo) if lo else 0.0, getattr(settings, hi))
        for key, lo, hi in _PLAUSIBLE
    ]


def nutrition_usable(nutrition: dict) -> bool:
    """Whether the estimated per-serving nutrition is trustworthy enough to use.

    Zero/absent calories means it was never derived, and values past the
    plausibility ceilings mean a measure was mis-parsed upstream. Either way we
    cannot honour a nutrition goal against it, so it is treated as unknown —
    the same call `classify_and_derive` makes when it hides nutrition rather
    than mislead.
    """
    n = nutrition or {}
    for key, floor, ceiling in plausible_bounds():
        if not (floor <= n.get(key, 0.0) <= ceiling):
            return False
    # Real food with real calories always has some protein. Zero means the macro
    # was never derived, and treating that as fact is how "low carb" started
    # matching a squid dish reporting 0 g protein and 0 g carbs. This is a
    # missing-data rule rather than a bound, which is why it sits outside the
    # table above.
    return n.get("protein_g", 0.0) > 0


def reconciles(nutrition: dict, tolerance: float = 0.3) -> bool:
    """Do the macros add up to the calorie total (4/4/9 kcal per gram)?

    Worth little against derived nutrition — calories and macros are summed from
    the same grams and the same per_100g table, so they agree by construction
    (21 of 7,533 corpus rows fail). It earns its keep only where the four numbers
    are produced independently, i.e. anything a model asserts.
    """
    n = nutrition or {}
    cal = n.get("calories", 0) or 0
    if not cal:
        return True
    implied = 4 * n.get("protein_g", 0) + 4 * n.get("carbs_g", 0) + 9 * n.get("fat_g", 0)
    return abs(cal - implied) <= tolerance * cal


# A dairy word preceded by one of these is a plant product, not dairy: coconut
# milk, peanut butter, oat milk. Scanning bare words marked 386 recipes as
# containing dairy, 341 of which then lost their vegan label.
_PLANT_QUALIFIERS = {
    "coconut", "almond", "soy", "soya", "oat", "rice", "cashew", "peanut",
    "groundnut", "hemp", "flax", "hazelnut", "macadamia", "cocoa", "shea",
    "nut", "plant", "vegan",
}
_QUALIFIABLE = {"milk", "butter", "cream", "cheese", "yogurt", "yoghurt", "curd"}
# Compounds where the dairy word leads and the whole phrase is still plant-based.
_PLANT_COMPOUNDS = r"butter\s*beans?|butter\s*nut|butternut|cream\s*of\s*(coconut|tartar)"


def _strip_plant_compounds(text: str) -> str:
    """Blank out dairy words that context makes plant-based.

    Only the qualified occurrence is removed, so a recipe listing both coconut
    milk and ordinary milk still trips on the second.
    """
    text = re.sub(_PLANT_COMPOUNDS, " ", text.lower())
    # Keep the qualifier, drop only the dairy word: "peanut butter" -> "peanut".
    # Blanking the whole phrase also erased the peanut/nut allergen signal, which
    # would have quietly removed the peanuts allergen from 257 recipes.
    return re.sub(
        rf"\b({'|'.join(_PLANT_QUALIFIERS)})[\s-]+({'|'.join(_QUALIFIABLE)})\b",
        r"\1",
        text,
    )


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
    # The keyword pass is a backstop for ingredients that did NOT resolve — a
    # resolved one already carries accurate vegan/allergen flags, and scanning
    # its name only invents false positives. Plant compounds are neutralized so
    # "coconut milk" cannot read as dairy in either the names or the title.
    raw_text = _strip_plant_compounds(" ".join(raw_names) + " " + title)
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
