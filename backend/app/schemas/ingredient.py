"""Ingredient autocomplete schema (Stage 5)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class IngredientSuggestion(BaseModel):
    name: str  # canonical ingredient name
    category: Optional[str] = None  # protein/vegetable/dairy/... (drives the token dot)
    matched_alias: Optional[str] = None  # the alias that matched, if not the name
