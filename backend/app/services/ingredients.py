"""Free-text ingredient name -> canonical ingredient id resolution.

The normalization spine for all retrieval. Callers pass raw pantry strings
("Cherry Tomatoes", "capsicum", "green onions") and get back canonical
ingredient ids plus the list of names that could not be resolved. Unknown
names are REPORTED, never raised — retrieval degrades gracefully.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ingredient, Recipe


def normalize(name: str) -> str:
    """Lowercase, strip, collapse whitespace, and naively singularize."""
    n = " ".join(name.strip().lower().split())
    if not n:
        return n
    # naive singularization on the last word only (tomatoes -> tomato)
    head, _, last = n.rpartition(" ")
    last = _singularize(last)
    return f"{head} {last}".strip() if head else last


def _singularize(word: str) -> str:
    if len(word) <= 3:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("oes"):  # tomatoes -> tomato, potatoes -> potato
        return word[:-2]
    if word.endswith("ses") or word.endswith("shes") or word.endswith("ches"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


@dataclass
class ResolvedPantry:
    ingredient_ids: list[int]
    matched_names: dict[int, str]  # ingredient_id -> canonical name
    unmatched: list[str]  # raw names that resolved to nothing


def resolve_pantry(session: Session, raw_names: list[str]) -> ResolvedPantry:
    """Resolve raw pantry strings to canonical ingredient ids."""
    ingredients = list(session.execute(select(Ingredient)).scalars())
    index: dict[str, int] = {}
    id_to_name: dict[int, str] = {}
    for ing in ingredients:
        id_to_name[ing.id] = ing.name
        index[normalize(ing.name)] = ing.id
        for alias in ing.aliases or []:
            index.setdefault(normalize(alias), ing.id)

    ids: list[int] = []
    matched: dict[int, str] = {}
    unmatched: list[str] = []
    seen: set[int] = set()

    for raw in raw_names:
        ing_id = index.get(normalize(raw))
        if ing_id is None:
            if raw.strip():
                unmatched.append(raw.strip())
            continue
        if ing_id not in seen:
            seen.add(ing_id)
            ids.append(ing_id)
            matched[ing_id] = id_to_name[ing_id]

    return ResolvedPantry(ingredient_ids=ids, matched_names=matched, unmatched=unmatched)


def disliked_recipe_ids(
    session: Session, recipe_ids: list[int], disliked_ingredients: list[str]
) -> set[int]:
    """Which of these recipes contain a disliked ingredient.

    Dislikes aren't a hard retrieval filter (they're a soft preference), so
    ranking demotes these ids rather than excluding them. Shared by the agent
    fallback and the /recommendations endpoint so both tiers behave the same.
    """
    disliked = {normalize(d) for d in disliked_ingredients}
    if not disliked or not recipe_ids:
        return set()
    rows = session.execute(
        select(Recipe.id, Recipe.ingredients).where(Recipe.id.in_(recipe_ids))
    ).all()
    hits: set[int] = set()
    for rid, ingredients in rows:
        names = {normalize(i["name"]) for i in (ingredients or [])}
        if disliked & names:
            hits.add(rid)
    return hits
