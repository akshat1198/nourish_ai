"""Generic pantry ingredients (e.g. "chicken" → chicken breast + thigh).

A generic is a data-driven alias for a *set* of canonical ingredients: picking
it in the pantry matches any recipe that uses ANY member, so a user isn't
locked to the one specific cut/variety they happened to select. Purely a
resolution/discovery concept — no DB rows, no properties of its own.

Loaded from seed_data/ingredient_groups.json (bundled into the image via the
Dockerfile's `COPY seed_data`). Groups take precedence over single-ingredient
aliases in `resolve_pantry`, so "chicken" expands to the set rather than
resolving to just chicken breast.
"""
from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Optional

_PATH = Path(__file__).resolve().parents[2] / "seed_data" / "ingredient_groups.json"


@functools.lru_cache(maxsize=1)
def load_groups() -> list[dict]:
    try:
        return json.loads(_PATH.read_text())
    except FileNotFoundError:  # groups are optional — degrade to none
        return []


@functools.lru_cache(maxsize=1)
def _index() -> dict[str, list[str]]:
    """Normalized generic name / alias → member canonical names."""
    from app.services.ingredients import normalize  # lazy: avoids import cycle

    idx: dict[str, list[str]] = {}
    for g in load_groups():
        members = g.get("members", [])
        for key in (g["generic"], *g.get("aliases", [])):
            idx.setdefault(normalize(key), members)
    return idx


def generic_members(normalized_name: str) -> Optional[list[str]]:
    """Member canonical names for a generic (by normalized name/alias), else None."""
    return _index().get(normalized_name)
