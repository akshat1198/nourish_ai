"""Schemas for GET /v1/search/web (Stage 6.5, Edamam link-out)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class WebSearchResult(BaseModel):
    title: str
    url: str                         # outbound link to the original recipe (per TOS)
    source: Optional[str] = None     # publisher name (e.g. "BBC Good Food")
    image_url: Optional[str] = None


class WebSearchResponse(BaseModel):
    # enabled=False when Edamam creds aren't configured — the UI shows a hint
    # instead of results (fail-open, like the LLM adapter).
    enabled: bool
    query: str
    attribution: str = "Recipe search powered by Edamam"
    results: list[WebSearchResult] = []
