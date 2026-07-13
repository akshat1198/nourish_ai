"""Ingredient autocomplete schema (Stage 5)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class IngredientSuggestion(BaseModel):
    name: str  # canonical ingredient name
    matched_alias: Optional[str] = None  # the alias that matched, if not the name
