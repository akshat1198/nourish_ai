"""Cuisine taxonomy — the backend mirror of frontend `lib/cuisines.ts`.

Two-level ids: a top-level `"indian"` or a child `"indian/gujarati"`. The
frontend sends these ids in `RecommendRequest.cuisines`; a recipe carries a
normalized `cuisine` (top level) + optional `region` (child). Matching is OR
across the selected ids; a top-level id matches any region under it.

Asian and Indian are separate top-level groups (per the user's questionnaire).
"""
from __future__ import annotations

from typing import Optional

CUISINE_TAXONOMY: dict[str, list[str]] = {
    "asian": ["chinese", "thai", "japanese", "filipino", "korean", "vietnamese"],
    # Indian regions expanded once the real corpus populated them
    # (each of these has 80+ recipes). The importer already stores these slugs.
    "indian": ["north_indian", "south_indian", "punjabi", "gujarati", "marathi",
               "bengali", "kerala", "tamil_nadu", "karnataka", "rajasthani",
               "andhra", "goan"],
    "italian": [],
    "mexican": [],
    "mediterranean": [],
    "middle-eastern": [],
    "american": [],
}

# Human labels for every id (top-level + "top/child"). Source of truth for the
# GET /v1/cuisines response; the frontend renders whatever the endpoint returns.
CUISINE_LABELS: dict[str, str] = {
    "asian": "Asian", "asian/chinese": "Chinese", "asian/thai": "Thai",
    "asian/japanese": "Japanese", "asian/filipino": "Filipino",
    "asian/korean": "Korean", "asian/vietnamese": "Vietnamese",
    "indian": "Indian", "indian/north_indian": "North Indian",
    "indian/south_indian": "South Indian", "indian/punjabi": "Punjabi",
    "indian/gujarati": "Gujarati", "indian/marathi": "Marathi",
    "indian/bengali": "Bengali", "indian/kerala": "Kerala",
    "indian/tamil_nadu": "Tamil Nadu", "indian/karnataka": "Karnataka",
    "indian/rajasthani": "Rajasthani", "indian/andhra": "Andhra",
    "indian/goan": "Goan", "italian": "Italian", "mexican": "Mexican",
    "mediterranean": "Mediterranean", "middle-eastern": "Middle Eastern",
    "american": "American",
}


def label_for(cid: str) -> str:
    """Human label for a cuisine id, with a titled fallback for unknown slugs."""
    return CUISINE_LABELS.get(cid, cid.split("/")[-1].replace("_", " ").title())

# All valid ids: "asian", "asian/chinese", "indian/gujarati", ...
VALID_CUISINE_IDS: set[str] = {
    top for top in CUISINE_TAXONOMY
} | {
    f"{top}/{child}" for top, children in CUISINE_TAXONOMY.items() for child in children
}


def parse_cuisine_id(cid: str) -> tuple[str, Optional[str]]:
    """`"indian/gujarati"` -> ("indian", "gujarati"); `"italian"` -> ("italian", None)."""
    top, _, region = cid.partition("/")
    return top, (region or None)


def cuisine_matches(
    recipe_cuisine: Optional[str],
    recipe_region: Optional[str],
    selected_ids: list[str],
) -> bool:
    """True if the recipe satisfies ANY selected cuisine id (OR semantics)."""
    if not selected_ids:
        return True
    if not recipe_cuisine:
        return False
    for cid in selected_ids:
        top, region = parse_cuisine_id(cid)
        if recipe_cuisine != top:
            continue
        if region is None or recipe_region == region:
            return True
    return False
