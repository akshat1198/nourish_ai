"""Persistent pantry schemas (Stage 5)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PantryItemIn(BaseModel):
    ingredient: str  # canonical name or alias (resolved server-side)
    is_staple: bool = False


class PantryItemOut(BaseModel):
    ingredient: str  # canonical name
    category: str | None = None  # drives the token dot
    is_staple: bool


class PantryReplaceIn(BaseModel):
    """PUT replaces the whole pantry (simplest correct protocol for a small set)."""

    items: list[PantryItemIn] = Field(default_factory=list)


class PantryResponse(BaseModel):
    items: list[PantryItemOut]
    unmatched: list[str] = Field(
        default_factory=list, description="Names that resolved to no known ingredient"
    )
