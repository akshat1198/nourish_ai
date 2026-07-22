"""Profile + recency-memory persistence.

SQL recency only — no embeddings, no cross-session summaries (that's a
deliberate scope fence).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InteractionHistory, Recipe, UserProfile
from app.schemas.profile import ProfileIn

RECENCY_DAYS = 7
RECENCY_LIMIT = 10


def load_profile(session: Session, user_key: str) -> Optional[UserProfile]:
    return session.get(UserProfile, user_key)


def upsert_profile(session: Session, user_key: str, data: ProfileIn) -> UserProfile:
    profile = session.get(UserProfile, user_key)
    if profile is None:
        profile = UserProfile(user_key=user_key)
        session.add(profile)
    profile.diet = data.diet
    profile.allergens = data.allergens
    profile.disliked_ingredients = data.disliked_ingredients
    profile.cuisine_prefs = data.cuisine_prefs
    session.commit()
    session.refresh(profile)
    return profile


def recent_recommended(session: Session, user_key: str) -> list[dict]:
    """Distinct recipes recommended to this user in the last RECENCY_DAYS, newest first."""
    since = datetime.now(timezone.utc) - timedelta(days=RECENCY_DAYS)
    rows = session.execute(
        select(InteractionHistory.recipe_id, Recipe.title)
        .join(Recipe, Recipe.id == InteractionHistory.recipe_id)
        .where(
            InteractionHistory.user_key == user_key,
            InteractionHistory.action == "recommended",
            InteractionHistory.created_at >= since,
        )
        .order_by(InteractionHistory.created_at.desc())
    ).all()
    seen, out = set(), []
    for recipe_id, title in rows:
        if recipe_id in seen:
            continue
        seen.add(recipe_id)
        out.append({"id": recipe_id, "title": title})
        if len(out) >= RECENCY_LIMIT:
            break
    return out


def feedback_state(session: Session, user_key: str) -> dict[int, dict]:
    """Derive current per-recipe feedback from the append-only log.

    Latest-wins per dimension: cooked/uncooked → `made`; liked/disliked/unrated
    → `rating`. "recommended" carries no user opinion, so it's ignored here.
    Only recipes with non-default state are returned.
    """
    rows = session.execute(
        select(InteractionHistory.recipe_id, InteractionHistory.action)
        .where(InteractionHistory.user_key == user_key)
        .order_by(InteractionHistory.created_at.asc(), InteractionHistory.id.asc())
    ).all()

    state: dict[int, dict] = {}
    for recipe_id, action in rows:
        cur = state.setdefault(recipe_id, {"made": False, "rating": None})
        if action == "cooked":
            cur["made"] = True
        elif action == "uncooked":
            cur["made"] = False
        elif action in ("liked", "disliked"):
            cur["rating"] = action
        elif action == "unrated":
            cur["rating"] = None

    return {
        rid: s
        for rid, s in state.items()
        if s["made"] or s["rating"] is not None
    }


def record_interaction(session: Session, user_key: str, recipe_id: int, action: str) -> None:
    session.add(
        InteractionHistory(user_key=user_key, recipe_id=recipe_id, action=action)
    )
    session.commit()


def record_recommendations(session: Session, user_key: str, recipe_ids: list[int]) -> None:
    for rid in recipe_ids:
        session.add(
            InteractionHistory(user_key=user_key, recipe_id=rid, action="recommended")
        )
    if recipe_ids:
        session.commit()
