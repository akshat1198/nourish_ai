"""Free-text pantry parsing.

Turns "half a bag of spinach, a couple eggs, some cheddar" into
["spinach", "eggs", "cheddar"] using the fast model. Fail-open: if the LLM is
disabled or errors, returns an empty list and logs — the deterministic pantry
list still drives retrieval.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.llm.client import LLMError, get_llm, is_enabled
from app.schemas.llm import ParsedPantry

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You extract grocery/pantry ingredients from casual free text. "
    "Return bare ingredient names: lowercase, singular, no quantities or "
    "adjectives (\"half a bag of baby spinach\" -> \"spinach\"). Ignore "
    "non-food words. If nothing food-related is present, return an empty list."
)


def parse_pantry_text(text: str) -> list[str]:
    if not text or not text.strip() or not is_enabled():
        return []
    try:
        result = get_llm().generate_structured(
            messages=[
                {"role": "user", "content": f"{_SYSTEM}\n\nText: {text}"},
            ],
            schema=ParsedPantry,
            model=settings.LLM_MODEL_FAST,
        )
    except LLMError as e:
        logger.warning("pantry_text parse failed, falling back to pantry list: %s", e)
        return []
    return [i.strip() for i in result.items if i and i.strip()]
