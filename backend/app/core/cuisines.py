"""Cuisine taxonomy (Stage 5) — the backend mirror of frontend `lib/cuisines.ts`.

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
    "indian": ["north_indian", "south_indian", "gujarati", "punjabi", "marathi", "bengali"],
    "italian": [],
    "mexican": [],
    "mediterranean": [],
    "middle-eastern": [],
    "american": [],
}

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
