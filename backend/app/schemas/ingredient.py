"""Ingredient autocomplete schema."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class IngredientSuggestion(BaseModel):
    name: str  # canonical ingredient name (or a generic group name)
    category: Optional[str] = None  # protein/vegetable/dairy/... (drives the token dot)
    matched_alias: Optional[str] = None  # the alias that matched, if not the name
    is_group: bool = False  # a generic that matches any of its members
    members: Optional[list[str]] = None  # member canonical names (groups only)
