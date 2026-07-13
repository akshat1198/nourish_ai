"""Request/response schemas for recipe recommendations."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    pantry: list[str] = Field(default_factory=list, description="On-hand ingredient names")
    pantry_text: Optional[str] = Field(
        None, description="Free-text pantry ('leftover chicken and a sad zucchini'); LLM-parsed and merged into pantry"
    )
    diet: Optional[str] = Field(
        None, description="Required diet label, e.g. vegan/vegetarian/gluten_free"
    )
    exclude_allergens: list[str] = Field(
        default_factory=list, description="Allergens to exclude, e.g. dairy, gluten, nuts"
    )
    max_time_minutes: Optional[int] = Field(None, ge=0)
    limit: int = Field(10, ge=1, le=50)


class IngredientMatch(BaseModel):
    name: str
    essential: bool


class RecipeCandidate(BaseModel):
    """A retrieved recipe with match stats (ranking is layered on in step 1.3)."""

    id: int
    title: str
    time_minutes: int
    diet_labels: list[str]
    allergens: list[str]
    tags: list[str]
    nutrition: dict
    matched_ingredients: list[str]
    missing_ingredients: list[str]
    matched_essential: int
    total_essential: int


class SubstitutionSuggestion(BaseModel):
    missing: str  # essential ingredient the recipe needs and pantry lacks
    use: str  # pantry ingredient that can substitute for it
    ratio: str


class RankedRecipe(RecipeCandidate):
    """A candidate with a computed relevance score and a human explanation."""

    score: float
    why: str
    substitutions: list[SubstitutionSuggestion] = Field(default_factory=list)


class RecommendResponse(BaseModel):
    results: list[RankedRecipe]
    mode: str = Field(
        "normal",
        description="normal | substitution_first | shopping_assisted (RETR-05 low-confidence fallback)",
    )
    explanation: Optional[str] = None
    unmatched_pantry: list[str] = Field(
        default_factory=list, description="Pantry names that resolved to no ingredient"
    )
