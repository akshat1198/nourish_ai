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


class ModifiedStep(BaseModel):
    index: int = Field(..., description="0-based index of the step being replaced")
    text: str = Field(..., description="Rewritten step text")


class ModifiedSteps(BaseModel):
    """Result of adapting a recipe's method for a single ingredient swap (7.3c)."""

    steps: list[ModifiedStep] = Field(
        default_factory=list, description="ONLY the steps that changed, by original index"
    )
    knock_on_flags: list[str] = Field(
        default_factory=list,
        description="Side effects to flag: cooking time, texture, binding, seasoning, moisture",
    )
    notes: str = Field("", description="Anything else worth flagging")
