"""Ingredient-line parsing + canonical matching for ingestion.

An ingredient line like "1 cup Tindora (Dondakaya/ Kovakkai) - finely chopped"
becomes ParsedLine(core="tindora", qty=1.0, unit="cup"). The matcher then maps
the core to a canonical ingredient name, or None.

Matching is deliberately PRECISE (exact normalized name/alias, plus stripping a
small set of trailing "form" words like powder/seeds/leaves), never head-noun
guessing — a false match would silently corrupt the allergen/diet/nutrition
derivation that reads canonical properties. Recall comes from growing the
vocabulary (6.2b), not from fuzzy matching.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from app.services.ingredients import normalize

# Unit tokens dropped when isolating the core name.
_UNITS = {
    "cup", "cups", "teaspoon", "teaspoons", "tsp", "tablespoon", "tablespoons",
    "tbsp", "gram", "grams", "g", "kg", "kilogram", "kilograms", "ml", "litre",
    "litres", "liter", "liters", "l", "pinch", "pinches", "handful", "handfuls",
    "clove", "cloves", "inch", "inches", "cm", "piece", "pieces", "slice",
    "slices", "sprig", "sprigs", "stalk", "stalks", "stick", "sticks", "bunch",
    "bunches", "can", "cans", "packet", "packets", "pack", "ounce", "ounces",
    "oz", "lb", "lbs", "pound", "pounds", "cube", "cubes", "ball", "balls",
    "small", "large", "medium", "big", "whole", "few", "little", "as", "per",
    "taste", "required", "needed", "approx", "approximately", "of", "a", "an",
}

# Unicode + written fractions -> float.
_FRAC = {
    "¼": 0.25, "½": 0.5, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 0.125,
    "⅜": 0.375, "⅝": 0.625, "⅞": 0.875, "⅕": 0.2, "⅖": 0.4, "⅗": 0.6,
}
# Trailing "form" words: stripping them lets "turmeric powder" -> "turmeric".
_FORM_WORDS = [
    "powder", "seeds", "seed", "leaves", "leaf", "paste", "sauce", "pods",
    "pod", "flakes", "sticks", "stick", "peeled", "grated", "chopped",
]

_NUM_TOKEN = re.compile(r"^[\d]+([./][\d]+)?$")
_PAREN = re.compile(r"\([^)]*\)")


@dataclass
class ParsedLine:
    core: str
    qty: Optional[float]
    unit: Optional[str]
    raw: str


def _parse_qty(tokens: list[str]) -> tuple[Optional[float], list[str]]:
    """Consume leading quantity tokens (incl. '1 1/2' and unicode fractions)."""
    qty = 0.0
    used = 0
    for tok in tokens:
        if tok in _FRAC:
            qty += _FRAC[tok]
            used += 1
            continue
        # bare unicode fraction glued to a number, e.g. "1½"
        m = re.match(r"^(\d+)?([¼½¾⅓⅔⅛⅜⅝⅞⅕⅖⅗])$", tok)
        if m:
            qty += (int(m.group(1)) if m.group(1) else 0) + _FRAC[m.group(2)]
            used += 1
            continue
        if _NUM_TOKEN.match(tok):
            if "/" in tok:
                n, d = tok.split("/")
                qty += float(n) / float(d) if float(d) else 0
            else:
                qty += float(tok)
            used += 1
            continue
        if re.match(r"^\d+-\d+$", tok):  # a range like "2-3" -> low end
            qty += float(tok.split("-")[0])
            used += 1
            continue
        break
    return (qty if used and qty else None), tokens[used:]


def parse_ingredient_line(line: str) -> ParsedLine:
    raw = (line or "").strip()
    s = raw.split(" - ")[0]              # drop prep note after " - "
    s = _PAREN.sub(" ", s)              # drop parentheticals (alt names)
    s = s.replace("﻿", "")             # stray BOM
    tokens = [t for t in re.split(r"[\s,]+", s.strip()) if t]
    qty, tokens = _parse_qty(tokens)
    unit = None
    if tokens and tokens[0].lower() in _UNITS and tokens[0].lower() not in {
        "of", "a", "an", "as", "per", "taste"
    }:
        unit = tokens[0].lower()
    core_tokens = [
        t.lower() for t in tokens
        if t.lower() not in _UNITS and not _NUM_TOKEN.match(t) and t not in _FRAC
    ]
    core = " ".join(core_tokens).strip(" .,-")
    return ParsedLine(core=core, qty=qty, unit=unit, raw=raw)


class CanonicalMatcher:
    """Maps a parsed core name to a canonical ingredient name, or None."""

    def __init__(self, ingredients: Iterable) -> None:
        # Accepts ORM Ingredient rows or dicts with name/aliases.
        self._index: dict[str, str] = {}
        for ing in ingredients:
            name = ing["name"] if isinstance(ing, dict) else ing.name
            aliases = (ing.get("aliases") if isinstance(ing, dict) else ing.aliases) or []
            self._index[normalize(name)] = name
            for a in aliases:
                self._index.setdefault(normalize(a), name)

    def match(self, core: str) -> Optional[str]:
        if not core:
            return None
        n = normalize(core)
        if n in self._index:
            return self._index[n]
        # Strip one trailing form-word and retry ("cinnamon stick" -> "cinnamon").
        words = n.split()
        if len(words) >= 2 and words[-1] in _FORM_WORDS:
            cand = normalize(" ".join(words[:-1]))
            if cand in self._index:
                return self._index[cand]
        return None

    @property
    def canonical_names(self) -> set[str]:
        return set(self._index.values())
