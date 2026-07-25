"""Deterministic mapping tables: raw source metadata -> our taxonomy.

Hand-authored from the full distinct-value lists in the Archana's dataset (82
cuisines / 20 courses / 10 diets) and TheMealDB areas. This IS the "hand-vetted
cuisine mapping" the plan calls for — the values are finite and legible, so an
LLM draft would only add noise. Unmappable catch-alls (Continental, Fusion,
European…) map to cuisine=None: still pantry-searchable, just not cuisine-filtered.

cuisine top-levels mirror app/core/cuisines.py: asian, indian, italian, mexican,
mediterranean, middle-eastern, american. region is a free-text slug — the 6
questionnaire regions use their exact taxonomy child ids (north_indian,
south_indian, gujarati, punjabi, marathi, bengali); everything else stores a
clean slug that a top-level "indian" pick still matches (a later pass may promote
high-count regions into the picker).
"""
from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Cuisine value -> (top_level, region_slug|None). Keys are the source strings
# AFTER stripping a trailing " Recipes", BOM, and surrounding whitespace
# (see normalize_cuisine_key). Unlisted keys -> (None, None).
# ---------------------------------------------------------------------------
_CUISINE_MAP: dict[str, tuple[Optional[str], Optional[str]]] = {
    # --- Indian: generic + regional -------------------------------------
    "indian": ("indian", None),
    "pakistani": ("indian", None),  # shared subcontinental cuisine
    "north indian": ("indian", "north_indian"),
    "south indian": ("indian", "south_indian"),
    "bengali": ("indian", "bengali"),
    "maharashtrian": ("indian", "marathi"),   # taxonomy child id is "marathi"
    "gujarati": ("indian", "gujarati"),
    "punjabi": ("indian", "punjabi"),
    "rajasthani": ("indian", "rajasthani"),
    "andhra": ("indian", "andhra"),
    "kerala": ("indian", "kerala"),
    "tamil nadu": ("indian", "tamil_nadu"),
    "kongunadu": ("indian", "tamil_nadu"),
    "chettinad": ("indian", "chettinad"),
    "karnataka": ("indian", "karnataka"),
    "coastal karnataka": ("indian", "karnataka"),
    "north karnataka": ("indian", "karnataka"),
    "south karnataka": ("indian", "karnataka"),
    "udupi": ("indian", "udupi"),
    "mangalorean": ("indian", "mangalorean"),
    "goan": ("indian", "goan"),
    "konkan": ("indian", "konkan"),
    "malvani": ("indian", "malvani"),
    "kashmiri": ("indian", "kashmiri"),
    "hyderabadi": ("indian", "hyderabadi"),
    "mughlai": ("indian", "mughlai"),
    "awadhi": ("indian", "awadhi"),
    "lucknowi": ("indian", "awadhi"),   # Lucknowi cuisine == Awadhi
    "parsi": ("indian", "parsi"),
    "sindhi": ("indian", "sindhi"),
    "oriya": ("indian", "oriya"),
    "bihari": ("indian", "bihari"),
    "jharkhand": ("indian", "jharkhand"),
    "assamese": ("indian", "assamese"),
    "north east india": ("indian", "north_east"),
    "nagaland": ("indian", "north_east"),
    "himachal": ("indian", "himachal"),
    "uttar pradesh": ("indian", "uttar_pradesh"),
    "uttarakhand-north kumaon": ("indian", "uttarakhand"),
    "haryana": ("indian", "haryana"),
    "malabar": ("indian", "malabar"),
    "coorg": ("indian", "coorg"),
    # --- Asian ----------------------------------------------------------
    "asian": ("asian", None),
    "thai": ("asian", "thai"),
    "chinese": ("asian", "chinese"),
    "cantonese": ("asian", "chinese"),
    "sichuan": ("asian", "chinese"),
    "hunan": ("asian", "chinese"),
    "shandong": ("asian", "chinese"),
    "indo chinese": ("asian", "chinese"),
    "japanese": ("asian", "japanese"),
    "korean": ("asian", "korean"),
    "vietnamese": ("asian", "vietnamese"),
    "indonesian": ("asian", "indonesian"),
    "malaysian": ("asian", "malaysian"),
    "burmese": ("asian", "burmese"),
    "nepalese": ("asian", "nepalese"),
    "sri lankan": ("asian", "sri_lankan"),
    # --- Rest of world (to the 7 top-levels) ----------------------------
    "italian": ("italian", None),
    "mexican": ("mexican", None),
    "mediterranean": ("mediterranean", None),
    "greek": ("mediterranean", "greek"),
    "middle eastern": ("middle-eastern", None),
    "arab": ("middle-eastern", None),
    "afghan": ("middle-eastern", None),
    "american": ("american", None),
    "french": ("european", "french"),
    "european": ("european", None),
    "british": ("european", "british"),
    "african": ("african", None),
    "caribbean": ("caribbean", None),
    # Deliberately unmapped -> (None, None): continental and fusion (catch-alls
    # covering 1156 rows between them — no honest cuisine to assign), jewish,
    # world breakfast, and the course-words that leak into the cuisine column
    # (appetizer, snack, side dish, dessert, dinner, lunch, brunch).
}


def normalize_cuisine_key(raw: str) -> str:
    key = (raw or "").replace("﻿", "").strip().lower()
    if key.endswith(" recipes"):
        key = key[: -len(" recipes")]
    return key.strip()


def map_cuisine(raw: str) -> tuple[Optional[str], Optional[str]]:
    """Raw source cuisine -> (cuisine_top_level, region_slug). (None, None) if unmapped."""
    return _CUISINE_MAP.get(normalize_cuisine_key(raw), (None, None))


# ---------------------------------------------------------------------------
# Course -> meal_types (subset of {breakfast, lunch, dinner, snack, dessert}).
# ---------------------------------------------------------------------------
_COURSE_MAP: dict[str, list[str]] = {
    "lunch": ["lunch"],
    "dinner": ["dinner"],
    "main course": ["lunch", "dinner"],
    "one pot dish": ["lunch", "dinner"],
    "side dish": ["lunch", "dinner"],
    "snack": ["snack"],
    "appetizer": ["snack"],
    "dessert": ["dessert"],
    "brunch": ["breakfast", "lunch"],
    "indian breakfast": ["breakfast"],
    "north indian breakfast": ["breakfast"],
    "south indian breakfast": ["breakfast"],
    "world breakfast": ["breakfast"],
}
# Diet-ish values that leak into the Course column -> a sensible savory default.
_COURSE_DEFAULT = ["lunch", "dinner"]


def map_course(raw: str) -> list[str]:
    key = (raw or "").replace("﻿", "").strip().lower()
    return _COURSE_MAP.get(key, _COURSE_DEFAULT)


# ---------------------------------------------------------------------------
# Diet -> SEED diet_labels. This is only a seed: allergen/diet derivation from
# matched ingredients (see derive()) refines it. Kept conservative so a
# mislabelled source row can't assert vegan/vegetarian the ingredients deny.
# ---------------------------------------------------------------------------
_DIET_MAP: dict[str, list[str]] = {
    "vegan": ["vegan", "vegetarian"],
    "vegetarian": ["vegetarian"],
    "high protein vegetarian": ["vegetarian", "high_protein"],
    "high protein non vegetarian": ["high_protein"],
    "gluten free": ["gluten_free"],
    # Not diet_labels in our vocab; left to ingredient derivation:
    "non vegeterian": [],          # (source's spelling)
    "eggetarian": [],              # contains eggs -> not asserted vegetarian
    "diabetic friendly": [],
    "no onion no garlic (sattvic)": ["vegetarian"],
    "sugar free diet": [],
}


def map_diet_seed(raw: str) -> list[str]:
    key = (raw or "").replace("﻿", "").strip().lower()
    return _DIET_MAP.get(key, [])


# ---------------------------------------------------------------------------
# TheMealDB "strArea" -> (cuisine, region). Their areas are nationalities.
# ---------------------------------------------------------------------------
_MEALDB_AREA_MAP: dict[str, tuple[Optional[str], Optional[str]]] = {
    "indian": ("indian", None),
    "chinese": ("asian", "chinese"),
    "thai": ("asian", "thai"),
    "japanese": ("asian", "japanese"),
    "vietnamese": ("asian", "vietnamese"),
    "filipino": ("asian", "filipino"),
    "malaysian": ("asian", "malaysian"),
    "italian": ("italian", None),
    "mexican": ("mexican", None),
    "greek": ("mediterranean", "greek"),
    "turkish": ("mediterranean", None),
    "moroccan": ("mediterranean", None),
    "tunisian": ("mediterranean", None),
    "egyptian": ("middle-eastern", None),
    "saudi arabian": ("middle-eastern", None),
    "syrian": ("middle-eastern", None),
    "american": ("american", None),
    "canadian": ("american", None),
    "european": ("european", None),
    "british": ("european", "british"),
    "irish": ("european", "irish"),
    "french": ("european", "french"),
    "spanish": ("european", "spanish"),
    "portuguese": ("european", "portuguese"),
    "dutch": ("european", "dutch"),
    "german": ("european", "german"),
    "polish": ("european", "polish"),
    "russian": ("european", "russian"),
    "ukrainian": ("european", "ukrainian"),
    "croatian": ("european", "croatian"),
    "norwegian": ("european", "norwegian"),
    "jamaican": ("caribbean", "jamaican"),
    "trinidadian": ("caribbean", "trinidadian"),
    "haitian": ("caribbean", "haitian"),
    "brazilian": ("latin-american", "brazilian"),
    "colombian": ("latin-american", "colombian"),
    "argentine": ("latin-american", "argentine"),
    "uruguayan": ("latin-american", "uruguayan"),
    "peruvian": ("latin-american", "peruvian"),
    "chilean": ("latin-american", "chilean"),
    "cuban": ("latin-american", "cuban"),
    "algerian": ("african", "algerian"),
    "kenyan": ("african", "kenyan"),
    "nigerian": ("african", "nigerian"),
    "ethiopian": ("african", "ethiopian"),
    "south african": ("african", "south_african"),
    # TheMealDB mixes nationalities with bare country names in the same column;
    # both spellings have to resolve or the recipe silently loses its cuisine.
    "india": ("indian", None),
    "united states": ("american", None),
    "france": ("european", "french"),
    "norway": ("european", "norwegian"),
    "netherlands": ("european", "dutch"),
    "slovakia": ("european", "slovak"),
    "venezuela": ("latin-american", "venezuelan"),
    "argentina": ("latin-american", "argentine"),
    # Still unmapped -> (None, None): australian (western-fusion, no honest
    # bucket here) and the rows TheMealDB ships with no area at all.
}


def map_mealdb_area(raw: str) -> tuple[Optional[str], Optional[str]]:
    return _MEALDB_AREA_MAP.get((raw or "").strip().lower(), (None, None))


# TheMealDB "strCategory" -> meal_types.
_MEALDB_CATEGORY_MAP: dict[str, list[str]] = {
    "breakfast": ["breakfast"],
    "dessert": ["dessert"],
    "starter": ["snack"],
    "side": ["lunch", "dinner"],
    "beef": ["lunch", "dinner"],
    "chicken": ["lunch", "dinner"],
    "lamb": ["lunch", "dinner"],
    "pork": ["lunch", "dinner"],
    "seafood": ["lunch", "dinner"],
    "goat": ["lunch", "dinner"],
    "pasta": ["lunch", "dinner"],
    "vegetarian": ["lunch", "dinner"],
    "vegan": ["lunch", "dinner"],
    "miscellaneous": ["lunch", "dinner"],
}


def map_mealdb_category(raw: str) -> list[str]:
    return _MEALDB_CATEGORY_MAP.get((raw or "").strip().lower(), ["lunch", "dinner"])
