"""Pull hard dietary constraints out of a free-text question, deterministically.

The planner endpoints take a plain-English `question`, and before this existed
the only thing that read it was the model. That quietly broke the invariant the
rest of the system is built on -- diet and allergen exclusion is a hard SQL
filter re-asserted by the validator, never a model's judgement. Asking for
"something high protein tonight, no dairy" with an empty `exclude_allergens`
returned two recipes carrying the dairy label and a clean `violations: []`,
because nothing deterministic had been told that dairy was excluded.

So the wording is matched here, against the same closed vocabulary the filter
UI uses, and the result is merged into the request BEFORE retrieval runs. The
model still reads the question for everything else; it just no longer decides
what is safe.

Deliberately conservative, in both directions:
  - A negation cue is required. "I love dairy" must not exclude dairy, and an
    over-eager match would quietly shrink someone's results for no stated reason.
  - Phrasings outside these patterns ("nothing from a cow") are simply not
    matched. That is a miss, not a false promise: `applied_constraints` on the
    response says exactly what was enforced, so the UI can show it rather than
    implying every constraint was understood.
"""
from __future__ import annotations

import re
from typing import Iterable

from app.core.allergens import ALLERGEN_VOCAB, remap_allergen

# Every spelling that should resolve to an allergen token, longest first so
# "tree nuts" wins over "nuts" when both could match at the same position.
_ALLERGEN_TERMS: list[str] = sorted(
    {
        *ALLERGEN_VOCAB,
        "milk", "cheese", "butter", "cream", "yogurt", "yoghurt",
        "wheat", "bread",
        "tree nuts", "tree nut", "nut", "peanut",
        "egg", "soya", "shell fish", "seafood", "prawns", "shrimp",
    },
    key=len,
    reverse=True,
)

# Dairy words that are not themselves the token; map them onto it.
_TERM_TO_ALLERGEN = {
    "cheese": "dairy", "butter": "dairy", "cream": "dairy",
    "yogurt": "dairy", "yoghurt": "dairy", "milk": "dairy",
    "bread": "gluten", "wheat": "gluten",
    "prawns": "shellfish", "shrimp": "shellfish", "seafood": "shellfish",
    "soya": "soy",
}

_NEGATION = r"(?:no|not|without|avoid|avoiding|skip|hold the|free of|free from|can't have|cannot have|allergic to|intolerant to)"

# "dairy-free", "gluten free", "nut-free"
_FREE_SUFFIX = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _ALLERGEN_TERMS) + r")[\s-]*free\b",
    re.IGNORECASE,
)
# "no dairy", "without any nuts", "allergic to shellfish"
_NEGATED = re.compile(
    _NEGATION + r"\s+(?:any\s+|more\s+|the\s+|all\s+)?(" + "|".join(re.escape(t) for t in _ALLERGEN_TERMS) + r")\b",
    re.IGNORECASE,
)

_DIET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("vegan", re.compile(r"\bvegan\b", re.IGNORECASE)),
    ("vegetarian", re.compile(r"\bvegetarian\b|\bveggie\b", re.IGNORECASE)),
    ("gluten_free", re.compile(r"\bgluten[\s-]*free\b|\bceliac\b|\bcoeliac\b", re.IGNORECASE)),
]


def _to_token(term: str) -> str:
    term = term.strip().lower()
    return _TERM_TO_ALLERGEN.get(term, remap_allergen(term))


def extract_constraints(question: str | None) -> tuple[str | None, list[str]]:
    """Return (diet, allergens) stated in the question. Both may be empty."""
    if not question:
        return None, []

    found: list[str] = []
    for pattern in (_FREE_SUFFIX, _NEGATED):
        for match in pattern.finditer(question):
            token = _to_token(match.group(1))
            if token in ALLERGEN_VOCAB and token not in found:
                found.append(token)

    diet: str | None = None
    for name, pattern in _DIET_PATTERNS:
        if pattern.search(question):
            # Vegan is the stricter reading of a "vegan vegetarian" muddle.
            if diet is None or name == "vegan":
                diet = name

    return diet, found


def merge_into_request(req, question: str | None) -> dict:
    """Apply what the question states to `req`, without overriding explicit values.

    Returns what was applied, so the caller can tell the user which constraints
    are actually being enforced rather than leaving them to assume.
    """
    diet, allergens = extract_constraints(question)

    applied_diet = None
    if diet and not req.diet:
        req.diet = diet
        applied_diet = diet

    applied_allergens = [a for a in allergens if a not in (req.exclude_allergens or [])]
    if applied_allergens:
        req.exclude_allergens = [*(req.exclude_allergens or []), *applied_allergens]

    return {"diet": applied_diet, "exclude_allergens": applied_allergens}


def implied_allergens(diet: str | None) -> list[str]:
    """Allergens a diet implies. Mirrors frontend `dietImpliedAllergens`."""
    return {
        "vegan": ["dairy", "eggs", "fish", "shellfish"],
        "vegetarian": ["fish", "shellfish"],
        "gluten_free": ["gluten"],
    }.get(diet or "", [])


def all_excluded(diet: str | None, allergens: Iterable[str]) -> list[str]:
    """The full exclusion set once the diet's implications are folded in."""
    out = list(allergens)
    for a in implied_allergens(diet):
        if a not in out:
            out.append(a)
    return out
