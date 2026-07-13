"""Schemas for LLM structured output (LLM-02)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedPantry(BaseModel):
    """Canonical-ish ingredient names extracted from free-text pantry input.

    The model normalizes descriptive phrasing ("half a bag of spinach") to bare
    ingredient names ("spinach"); alias resolution still happens downstream in
    resolve_pantry(), so the model doesn't need the canonical vocabulary.
    """

    items: list[str] = Field(
        default_factory=list, description="Bare ingredient names, lowercase, singular"
    )
    notes: str = Field("", description="Anything ambiguous or worth flagging")
