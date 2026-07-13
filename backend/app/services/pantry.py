"""Persistent pantry (Stage 5).

Rows keyed by the authed `user_key`. PUT replaces the whole set (simplest
correct protocol for a small per-user list). Names resolve through the same
canonical index as retrieval, so a stored pantry item always matches recipes.
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Ingredient, PantryItem
from app.schemas.pantry import PantryItemIn, PantryItemOut
from app.services.ingredients import normalize


def _name_index(session: Session) -> dict[str, tuple[int, str]]:
    """normalized name/alias -> (ingredient_id, canonical_name)."""
    index: dict[str, tuple[int, str]] = {}
    for ing in session.execute(select(Ingredient)).scalars():
        index[normalize(ing.name)] = (ing.id, ing.name)
        for alias in ing.aliases or []:
            index.setdefault(normalize(alias), (ing.id, ing.name))
    return index


def get_pantry(session: Session, user_key: str) -> list[PantryItemOut]:
    rows = session.execute(
        select(Ingredient.name, PantryItem.is_staple)
        .join(Ingredient, Ingredient.id == PantryItem.ingredient_id)
        .where(PantryItem.user_key == user_key)
        .order_by(Ingredient.name)
    ).all()
    return [PantryItemOut(ingredient=name, is_staple=bool(staple)) for name, staple in rows]


def replace_pantry(
    session: Session, user_key: str, items: list[PantryItemIn]
) -> tuple[list[PantryItemOut], list[str]]:
    index = _name_index(session)
    resolved: dict[int, tuple[str, bool]] = {}  # id -> (canonical_name, is_staple)
    unmatched: list[str] = []
    for it in items:
        hit = index.get(normalize(it.ingredient))
        if hit is None:
            if it.ingredient.strip():
                unmatched.append(it.ingredient.strip())
            continue
        iid, cname = hit
        prev = resolved.get(iid)
        # dedup: staple wins if the same ingredient appears twice
        resolved[iid] = (cname, (prev[1] if prev else False) or it.is_staple)

    session.execute(delete(PantryItem).where(PantryItem.user_key == user_key))
    for iid, (_, staple) in resolved.items():
        session.add(PantryItem(user_key=user_key, ingredient_id=iid, is_staple=staple))
    session.commit()

    out = sorted(
        (PantryItemOut(ingredient=cname, is_staple=staple) for cname, staple in resolved.values()),
        key=lambda p: p.ingredient,
    )
    return out, unmatched
