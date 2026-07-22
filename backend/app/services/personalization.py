"""Learned personalization (Stage 12).

A per-user "taste vector" — the mean embedding of recipes the user has
saved/cooked/liked, minus a fraction of ones they've disliked — used to gently
reorder an ALREADY-filtered/ranked candidate pool. This module never touches
retrieval or hard filters; `ranking.py` applies the resulting scores strictly
after `_passes_filters`, so personalization can only reorder the safe set, never
surface a diet/allergen violation.

Degrades to a no-op ({} / None) on: cold start (no positive signal), Redis
down, or an all-NULL-embedding candidate set — identical to pre-Stage-12
behaviour in every one of those cases.
"""
from __future__ import annotations

import json
from typing import Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import redis_client
from app.core.config import settings
from app.models import InteractionHistory, Recipe, SavedRecipe


def positive_recipe_ids(session: Session, user_key: str) -> set[int]:
    """Saved recipes UNION cooked/liked recipes (Stage 9/10 signals)."""
    saved = session.execute(
        select(SavedRecipe.recipe_id).where(SavedRecipe.user_key == user_key)
    ).scalars()
    interacted = session.execute(
        select(InteractionHistory.recipe_id).where(
            InteractionHistory.user_key == user_key,
            InteractionHistory.action.in_(("cooked", "liked")),
        )
    ).scalars()
    return set(saved) | set(interacted)


def negative_recipe_ids(session: Session, user_key: str) -> set[int]:
    """Disliked recipes (Stage 9 signal)."""
    disliked = session.execute(
        select(InteractionHistory.recipe_id).where(
            InteractionHistory.user_key == user_key,
            InteractionHistory.action == "disliked",
        )
    ).scalars()
    return set(disliked)


def _embeddings(session: Session, ids: set[int]) -> list[list[float]]:
    if not ids:
        return []
    rows = session.execute(
        select(Recipe.embedding).where(
            Recipe.id.in_(ids), Recipe.embedding.isnot(None)
        )
    ).scalars()
    return [list(v) for v in rows if v is not None]


def _mean_vec(vectors: list[list[float]]) -> Optional[np.ndarray]:
    if not vectors:
        return None
    return np.mean(np.asarray(vectors, dtype=float), axis=0)


def _taste_cache_key(user_key: str) -> str:
    return f"taste:{user_key}:{settings.RANKING_VERSION}"


def invalidate_taste_cache(user_key: str) -> None:
    """Bust the cached taste vector so the next recommend recomputes fresh.

    Any feedback write (cooked/liked/disliked/etc.) can change this user's
    positive or negative recipe set — without this, a dismiss (or a like)
    could take up to TASTE_CACHE_TTL to visibly affect ranking. Best-effort,
    same as the rest of this module: Redis down is a no-op, never raises.
    """
    try:
        redis_client.delete(_taste_cache_key(user_key))
    except Exception:
        pass


def taste_vector(session: Session, user_key: str) -> Optional[list[float]]:
    """The user's taste vector, cached in Redis. None on cold start (no
    positive signal with a usable embedding) — callers must treat that as
    "personalization off" for this user, not an error."""
    cache_key = _taste_cache_key(user_key)
    try:
        cached = redis_client.get(cache_key)
        if cached is not None:
            return json.loads(cached)
    except Exception:
        pass  # Redis down -> compute uncached, never raise

    pos_vecs = _embeddings(session, positive_recipe_ids(session, user_key))
    pos = _mean_vec(pos_vecs)
    if pos is None:
        return None  # cold start: no positive signal with an embedding

    neg_vecs = _embeddings(session, negative_recipe_ids(session, user_key))
    neg = _mean_vec(neg_vecs)
    vec = pos if neg is None else pos - settings.TASTE_NEG_WEIGHT * neg
    result = vec.tolist()

    try:
        redis_client.set(cache_key, json.dumps(result), ex=settings.TASTE_CACHE_TTL)
    except Exception:
        pass  # Redis down -> just don't cache

    return result


def taste_scores(
    session: Session,
    user_key: str,
    recipe_ids: list[int],
    vec: Optional[list[float]] = None,
) -> dict[int, float]:
    """Cosine similarity of each candidate's embedding to the taste vector.

    Returns {} when there's no taste vector (cold start / disabled) or none of
    the candidates have an embedding — both are safe, additive no-ops for the
    caller (ranking.py treats a missing entry as 0.0 taste contribution).
    """
    vec = vec if vec is not None else taste_vector(session, user_key)
    if vec is None or not recipe_ids:
        return {}

    tvec = np.asarray(vec, dtype=float)
    tnorm = np.linalg.norm(tvec)
    if tnorm == 0:
        return {}

    rows = session.execute(
        select(Recipe.id, Recipe.embedding).where(
            Recipe.id.in_(recipe_ids), Recipe.embedding.isnot(None)
        )
    ).all()

    scores: dict[int, float] = {}
    for rid, emb in rows:
        if emb is None:
            continue
        rvec = np.asarray(list(emb), dtype=float)
        rnorm = np.linalg.norm(rvec)
        if rnorm == 0:
            continue
        scores[rid] = float(np.dot(tvec, rvec) / (tnorm * rnorm))
    return scores
