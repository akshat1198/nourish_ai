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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from app.models import Ingredient, Recipe, RecipeIngredient
# classify_and_derive + measure_to_grams moved to app.services.derivation (7.3a,
# 7.3f); re-exported so the importers' `from scripts.ingest.pipeline import ...` hold.
from app.services.derivation import (  # noqa: F401
    classify_and_derive,
    ingredient_columns,
    measure_to_grams,
)
from app.services.ingredients import normalize
from scripts.ingest.normalize import CanonicalMatcher

SEED = Path(__file__).resolve().parents[2] / "seed_data"


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
            row = Ingredient(**ingredient_columns(spec))
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


def title_exists(session, title: str) -> bool:
    norm = normalize(title)
    rows = session.execute(select(Recipe.title)).scalars()
    return any(normalize(t) == norm for t in rows)


class Deduper:
    """In-memory title+source_url dedup, pre-loaded once. O(1) per recipe —
    essential for the 6,871-row Archana's import (per-recipe DB title scans would
    be O(n²))."""

    def __init__(self, session) -> None:
        self.titles = {normalize(t) for t in session.execute(select(Recipe.title)).scalars()}
        self.urls = {u for u in session.execute(select(Recipe.source_url)).scalars() if u}

    def is_dup(self, title: str, url: Optional[str]) -> bool:
        return normalize(title) in self.titles or bool(url and url in self.urls)

    def add(self, title: str, url: Optional[str]) -> None:
        self.titles.add(normalize(title))
        if url:
            self.urls.add(url)


def upsert_recipe(session, name_to_id: dict, fields: dict, matched_items: list[tuple],
                  deduper: Optional[Deduper] = None) -> str:
    """matched_items: (canonical_name, qty, unit, essential). Returns status.

    Pass a Deduper for O(1) dedup (bulk imports); without it, falls back to
    per-call DB scans (fine for the small TheMealDB set).
    """
    url = fields.get("source_url")
    if deduper is not None:
        if deduper.is_dup(fields["title"], url):
            return "dup_source" if url and url in deduper.urls else "dup_title"
        deduper.add(fields["title"], url)
    else:
        exists = session.execute(
            select(Recipe.id).where(Recipe.source == fields["source"],
                                    Recipe.source_url == url)
        ).first()
        if exists and url:
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
