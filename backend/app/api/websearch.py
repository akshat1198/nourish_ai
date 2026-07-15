"""GET /v1/search/web (Stage 6.5) — Edamam link-out for "search the wider web".

Discovery only: proxies Edamam live and returns outbound links; nothing is
stored, and these results never enter pantry-matching/ranking (that stays the
own-DB corpus). Off (enabled=false) when Edamam creds aren't set.
"""
from fastapi import APIRouter, Depends, Query

from app.api.auth import get_current_user_key
from app.schemas.websearch import WebSearchResponse
from app.services import edamam

router = APIRouter(prefix="/v1", tags=["websearch"])


@router.get("/search/web", response_model=WebSearchResponse)
def search_web(
    q: str = Query("", max_length=120),
    user_key: str = Depends(get_current_user_key),
):
    return WebSearchResponse(
        enabled=edamam.is_enabled(),
        query=q.strip(),
        results=edamam.search_web(q, user_key),
    )
