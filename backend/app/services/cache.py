"""Recommendation response cache (RETR-04).

Keyed on a canonical hash of the request (order-independent pantry/allergens)
plus RANKING_VERSION, so a weight change transparently invalidates the cache.
Hit/miss counters are kept in Redis and surfaced at GET /v1/metrics/cache.
Redis being unavailable degrades to a cache miss — it never breaks a request.
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from app.cache import redis_client
from app.core.config import settings

HITS_KEY = "metrics:cache:hits"
MISSES_KEY = "metrics:cache:misses"


def recommend_key(payload: dict) -> str:
    """Stable cache key. Lists that are semantically sets are sorted first.

    `mode` is part of the key: sql and hybrid produce different results for the
    same request and must not share a cache entry.
    """
    canonical = {
        "pantry": sorted(payload.get("pantry") or []),
        "pantry_text": (payload.get("pantry_text") or "").strip().lower(),
        "diet": payload.get("diet"),
        "exclude_allergens": sorted(payload.get("exclude_allergens") or []),
        "disliked_ingredients": sorted(payload.get("disliked_ingredients") or []),
        "cuisines": sorted(payload.get("cuisines") or []),
        "meal_type": payload.get("meal_type"),
        "nutrition_goals": sorted(payload.get("nutrition_goals") or []),
        "max_time_minutes": payload.get("max_time_minutes"),
        "limit": payload.get("limit"),
        "mode": payload.get("mode", "hybrid"),
        # Stage 12: personalized results must not collide across users. None
        # for every unpersonalized request (cold-start users, or the feature
        # disabled) so the shared cache is preserved when there's no taste term.
        "user": payload.get("user"),
        # Stage 13: the A/B variant changes results (control never
        # personalizes) so it must fork the cache too; None with no session_id.
        "variant": payload.get("variant"),
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(blob.encode()).hexdigest()
    return f"rec:{digest}:{settings.RANKING_VERSION}"


def get_cached(key: str) -> Optional[dict]:
    try:
        raw = redis_client.get(key)
        if raw is None:
            redis_client.incr(MISSES_KEY)
            return None
        redis_client.incr(HITS_KEY)
        return json.loads(raw)
    except Exception:
        return None  # Redis down -> treat as miss, never raise


def set_cached(key: str, value: dict) -> None:
    try:
        redis_client.set(
            key, json.dumps(value), ex=settings.CACHE_TTL_SECONDS
        )
    except Exception:
        pass


def cache_metrics() -> dict:
    try:
        hits = int(redis_client.get(HITS_KEY) or 0)
        misses = int(redis_client.get(MISSES_KEY) or 0)
    except Exception:
        hits = misses = 0
    total = hits + misses
    return {
        "hits": hits,
        "misses": misses,
        "hit_rate": round(hits / total, 4) if total else 0.0,
    }
