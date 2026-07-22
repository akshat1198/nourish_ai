"""Single source of truth for the allergen vocabulary.

Every backend surface that produces or consumes allergen tokens imports from
here — derivation (ingest pipeline), the enrichment prompt, the merge cleaner,
request normalization, and tests — so the tokens can't drift the way an
"egg" (seed) vs "eggs" (filter) mismatch once did. The frontend keeps its
own copy in `lib/filter-options.ts` (Python can't import TS); a test asserts the
two lists stay identical.

Order matches the frontend list so any UI that renders in vocab order agrees.
"""
from __future__ import annotations

from typing import Iterable, Optional

# The canonical allergen labels, in the same order as the frontend UI.
ALLERGEN_VOCAB: tuple[str, ...] = (
    "dairy", "gluten", "nuts", "peanuts", "eggs", "soy", "shellfish", "fish", "sesame",
)
ALLERGEN_SET: frozenset[str] = frozenset(ALLERGEN_VOCAB)

# Common near-variants LLMs / hand-authored data emit -> the canonical token.
_REMAP: dict[str, str] = {
    "tree nuts": "nuts", "tree nut": "nuts", "treenuts": "nuts", "nut": "nuts",
    "egg": "eggs", "milk": "dairy", "wheat": "gluten", "peanut": "peanuts",
    "shell fish": "shellfish", "seafood": "shellfish",
}


def remap_allergen(token: str) -> str:
    """Canonicalize a single token's known variants; unknown tokens pass through."""
    return _REMAP.get(str(token).strip().lower(), str(token).strip().lower())


def clean_allergens(tokens: Iterable[str]) -> list[str]:
    """Normalize + keep only in-vocab tokens, deduped, in vocab order.

    Use for DATA we control (derivation, seed, enrichment) where an off-vocab
    token is a mistake to drop. Request-side normalization uses remap_allergen
    directly so a user's token is never silently discarded.
    """
    seen = {remap_allergen(t) for t in tokens}
    return [t for t in ALLERGEN_VOCAB if t in seen]


def normalize_request_allergens(tokens: Iterable[str]) -> list[str]:
    """Remap variants but KEEP unknowns (a filter no-op, never a silent drop)."""
    out: list[str] = []
    for t in tokens:
        r = remap_allergen(t)
        if r and r not in out:
            out.append(r)
    return out
