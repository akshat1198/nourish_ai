"""Shopping list schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ShoppingListRequest(BaseModel):
    recipe_ids: list[int] = Field(..., min_length=1)
    pantry: list[str] = Field(default_factory=list)


class ShoppingItem(BaseModel):
    name: str
    unit: Optional[str] = None
    total_qty: Optional[float] = Field(
        None, description="Summed quantity in `unit`; null if any source qty was unknown"
    )
    needed_for: list[str] = Field(
        default_factory=list, description="Titles of recipes needing this ingredient"
    )


class ShoppingListResponse(BaseModel):
    items: list[ShoppingItem]
    unmatched_pantry: list[str] = Field(default_factory=list)
    missing_recipe_ids: list[int] = Field(
        default_factory=list, description="Requested ids not found in the catalog"
    )
