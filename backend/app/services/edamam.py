"""Edamam Recipe Search proxy (Stage 6.5) — supplemental web discovery.

Live link-out ONLY: results are returned to the caller and never stored or fed
into pantry-matching/ranking (Edamam TOS forbids caching their content in our
own retrieval DB — the same reason Spoonacular was rejected). Fail-open: with
no credentials the feature is simply off.
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.schemas.websearch import WebSearchResult

logger = logging.getLogger(__name__)

_API = "https://api.edamam.com/api/recipes/v2"
_TIMEOUT = 8.0


def is_enabled() -> bool:
    return bool(settings.EDAMAM_APP_ID and settings.EDAMAM_APP_KEY)


def search_web(query: str, user_key: str, limit: int = 12) -> list[WebSearchResult]:
    """Query Edamam; return normalized results. Errors -> [] (never raise)."""
    query = (query or "").strip()
    if not query or not is_enabled():
        return []
    params = {
        "type": "public",
        "q": query,
        "app_id": settings.EDAMAM_APP_ID,
        "app_key": settings.EDAMAM_APP_KEY,
    }
    # v2 requires an account-user header; the opaque per-user key is a fine value.
    headers = {"Edamam-Account-User": user_key or "nourish"}
    try:
        resp = httpx.get(_API, params=params, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("edamam search failed: %s", e)
        return []

    results: list[WebSearchResult] = []
    for hit in hits[:limit]:
        r = hit.get("recipe") or {}
        url = r.get("url")
        label = r.get("label")
        if not url or not label:
            continue
        results.append(
            WebSearchResult(
                title=label,
                url=url,
                source=r.get("source"),
                image_url=r.get("image"),
            )
        )
    return results
