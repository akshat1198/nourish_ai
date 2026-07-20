"""Response schema for the recipe detail endpoint (Stage 7.1).

Surfaces the recipe fields that `RankedRecipe` drops for the list view — steps,
servings, the display ingredient list, provenance, and the honesty flag on
estimated nutrition — so the detail page renders entirely from our own data.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RecipeIngredientLine(BaseModel):
    """One display ingredient line, enriched with its canonical category dot.

    `qty` is present for seed/archanas rows and null for themealdb, where the
    raw measure ("1 cup") lives in `unit` — the frontend scaler handles both.
    `category` is None when the display name doesn't resolve to the vocabulary.
    """

    name: str
    qty: Optional[float] = None
    unit: Optional[str] = None
    essential: bool = True
    category: Optional[str] = None


class RecipeDetail(BaseModel):
    id: int
    title: str
    description: str = ""
    cuisine: Optional[str] = None
    region: Optional[str] = None
    meal_types: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    diet_labels: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    time_minutes: int
    servings: int
    nutrition: dict = Field(default_factory=dict)
    nutrition_estimated: bool = False
    ingredients: list[RecipeIngredientLine] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    # Provenance (Stage 6): seed rows have neither url nor attribution.
    source: str
    source_url: Optional[str] = None
    attribution: Optional[str] = None
    image_url: Optional[str] = None
    license_note: Optional[str] = None
