"""Response schema for the recipe detail endpoint (Stage 7.1).

Surfaces the recipe fields that `RankedRecipe` drops for the list view — steps,
servings, the display ingredient list, provenance, and the honesty flag on
estimated nutrition — so the detail page renders entirely from our own data.
"""
from __future__ import annotations

from typing import Literal, Optional

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


# --------------------------------------------------------------------------- #
# Substitution-aware modification (Stage 7.3)
# --------------------------------------------------------------------------- #
class ModifyRequest(BaseModel):
    # "swap" needs to_ingredient; "remove" adapts the recipe without from_ingredient.
    op: Literal["swap", "remove"] = "swap"
    from_ingredient: str = Field(..., max_length=80)
    to_ingredient: Optional[str] = Field(None, max_length=80)


class SwapInfo(BaseModel):
    from_ingredient: str
    to_ingredient: str
    ratio: str


class ModifyResponse(BaseModel):
    recipe_id: int
    title: str
    operation: str = "swap"  # "swap" | "remove" — drives the banner wording
    # For a removal: a one-line summary of what was done (omitted, or substituted).
    note: str = ""
    swap: SwapInfo
    ingredients: list[RecipeIngredientLine]
    steps: list[str]
    # Indexes of steps the LLM rewrote (7.3c); empty in the deterministic core.
    changed_step_indexes: list[int] = Field(default_factory=list)
    diet_labels: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    # Diff vs the original recipe's allergens — the safety payoff of the swap.
    added_allergens: list[str] = Field(default_factory=list)
    removed_allergens: list[str] = Field(default_factory=list)
    # Estimated post-swap per-serving nutrition + the signed macro delta ({} when
    # it can't be estimated — then a warning says nutrition is unchanged).
    nutrition: dict = Field(default_factory=dict)
    nutrition_delta: dict = Field(default_factory=dict)
    knock_on_flags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    llm_used: bool = False
    # True when the target isn't in our verified vocabulary and the swap (labels
    # + nutrition) was estimated by the LLM — the UI flags it as approximate.
    approximate: bool = False
