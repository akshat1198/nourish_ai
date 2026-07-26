"""Structured output for recipe generation.

These shapes are what the model is asked to fill; nothing here is trusted. The
diet/allergen labels a generated recipe ends up with are re-derived from its
ingredients by `classify_and_derive`, never taken from the model — a model that
says "vegan" while listing paneer is the exact failure the validator exists to
catch (see `agent/validator.py`).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.core.allergens import ALLERGEN_VOCAB

# Categories and units the vocabulary already uses. Constraining the model to
# them keeps a new ingredient indexable by the same ranking weights as the rest.
INGREDIENT_CATEGORIES = (
    "protein", "vegetable", "fruit", "dairy", "grain", "starch",
    "herb", "spice", "sauce", "pantry",
)
INGREDIENT_UNITS = ("g", "ml", "unit", "cup", "tbsp", "tsp", "clove", "slice", "stalk")


class Macros(BaseModel):
    calories: float = Field(..., ge=0, description="kcal per 100 g")
    protein_g: float = Field(..., ge=0)
    carbs_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)


class NewIngredient(BaseModel):
    """A canonical ingredient the vocabulary doesn't have yet.

    Required so an authentic recipe isn't limited to the 275 ingredients we
    started with — but every field is range-checked before insert, because a
    hallucinated per_100g would silently corrupt the nutrition of every recipe
    that later uses this ingredient.
    """

    name: str = Field(..., description="Lowercase singular canonical name, e.g. 'fish sauce'")
    category: str = Field(..., description=f"One of: {', '.join(INGREDIENT_CATEGORIES)}")
    aliases: list[str] = Field(default_factory=list, description="Other common names")
    vegetarian: bool
    vegan: bool
    allergens: list[str] = Field(
        default_factory=list, description=f"Any of: {', '.join(ALLERGEN_VOCAB)}"
    )
    per_100g: Macros
    default_unit: str = Field("g", description=f"One of: {', '.join(INGREDIENT_UNITS)}")
    grams_per_piece: float = Field(
        ..., gt=0, description="What one bare unit weighs: a piece if countable, else a cup"
    )


class GeneratedIngredientLine(BaseModel):
    name: str = Field(..., description="Ingredient name, matching the vocabulary where possible")
    qty: Optional[float] = Field(None, description="Numeric quantity")
    unit: Optional[str] = Field(None, description="g, ml, cup, tbsp, tsp, or blank for whole pieces")
    essential: bool = Field(True, description="False only for optional garnishes")


class GeneratedRecipe(BaseModel):
    title: str
    description: str = Field("", description="One appetizing sentence")
    cuisine: Optional[str] = Field(None, description="Top-level cuisine id requested")
    region: Optional[str] = Field(None, description="Sub-cuisine id, if one was requested")
    meal_types: list[str] = Field(default_factory=list)
    time_minutes: int = Field(..., gt=0)
    servings: int = Field(2, gt=0)
    ingredients: list[GeneratedIngredientLine] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list, description="Numbered method, one step per entry")


class GenerationResult(BaseModel):
    """What one generation call returns."""

    recipes: list[GeneratedRecipe] = Field(default_factory=list)
    new_ingredients: list[NewIngredient] = Field(
        default_factory=list,
        description="Canonical entries for any ingredient not already in the vocabulary",
    )
