"""Schemas for LLM structured output."""
from __future__ import annotations

from typing import Optional

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


# --------------------------------------------------------------------------- #
# Substitution suggestions + free-text adaptation
# --------------------------------------------------------------------------- #
class SuggestedSwap(BaseModel):
    use: str = Field(..., description="The substitute ingredient name")
    ratio: str = Field("1:1", description="original:substitute quantity ratio, e.g. 1:1 or 1:0.75")
    note: str = Field("", description="Short why/how it works, <= 12 words")
    enables_diets: list[str] = Field(
        default_factory=list, description="Diets this swap enables: vegan, vegetarian, gluten_free, dairy_free"
    )


class SuggestedSwaps(BaseModel):
    """LLM-proposed alternatives for one ingredient, realistic and common."""

    substitutes: list[SuggestedSwap] = Field(default_factory=list)


class MacroDelta(BaseModel):
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0


class FreeSwapAdaptation(BaseModel):
    """Adapt a recipe for a swap to an ingredient outside our vocabulary.

    Everything here is the model's best estimate — the caller flags the result
    as approximate."""

    ratio: str = Field("1:1", description="original:substitute quantity ratio")
    changed_steps: list[ModifiedStep] = Field(
        default_factory=list, description="ONLY steps that change, by 0-based original index"
    )
    knock_on_flags: list[str] = Field(
        default_factory=list, description="Side effects: cooking time, texture, binding, moisture"
    )
    added_allergens: list[str] = Field(
        default_factory=list, description="Allergens the substitute introduces (dairy, gluten, nuts, egg, soy, shellfish, fish)"
    )
    removed_allergens: list[str] = Field(
        default_factory=list, description="Allergens no longer present after the swap"
    )
    enables_diets: list[str] = Field(
        default_factory=list, description="Diets now satisfied (vegan, vegetarian, gluten_free, dairy_free)"
    )
    breaks_diets: list[str] = Field(
        default_factory=list, description="Diets no longer satisfied after the swap"
    )
    nutrition_delta: Optional[MacroDelta] = Field(
        None, description="Approx signed per-serving change; omit if genuinely unsure"
    )
    note: str = Field("", description="One-line summary of the adaptation")


class EnrichedRecipe(BaseModel):
    """Clearer method + filled-in measures for one recipe. Both fields are
    plain string lists on purpose — nested/optional schemas blow the
    structured-output grammar budget (see RemovalPlan)."""

    steps: list[str] = Field(
        default_factory=list,
        description="The rewritten steps — SAME count and order, each with prep state and cooking cues; invent no new ingredients",
    )
    quantities: list[str] = Field(
        default_factory=list,
        description="A typical measure for EACH listed measure-less ingredient, in the SAME order, e.g. '1 teaspoon' or 'to taste'",
    )


class RemovalPlan(BaseModel):
    """The creative part of removing an ingredient. Deliberately SMALL — a
    larger schema blows the structured-output grammar budget ("Grammar
    compilation timed out"). Allergens, diet, and nutrition are re-derived
    deterministically in code, not by the model."""

    # Plain string (not a Literal enum) — enums also inflate grammar compilation.
    strategy: str = Field(
        "omit", description="'omit' to leave it out, or 'substitute' to use an alternative"
    )
    substitute: str = Field("", description="If substituting: the ingredient to use instead")
    ratio: str = Field("1:1", description="removed:substitute ratio (if substituting)")
    changed_steps: list[ModifiedStep] = Field(
        default_factory=list, description="ONLY steps that change, by 0-based original index"
    )
    knock_on_flags: list[str] = Field(
        default_factory=list, description="Side effects: texture, binding, moisture, flavour"
    )
    note: str = Field(
        "", description="One line: what you did and how to compensate, e.g. 'Left out the cashews — add 1 tbsp cream for richness.'"
    )


class EstimatedNutrition(BaseModel):
    """Per-serving macros for one recipe whose derived nutrition was unusable.

    Five flat scalars on purpose — nested or enum fields blow the
    structured-output grammar budget (see RemovalPlan). Nothing here is trusted
    on arrival: the values are range-checked and reconciled against each other
    before anything is stored.
    """

    # Required, unlike the other schemas here: with defaults the model could
    # return an empty object and the result parsed as a confident set of zeros,
    # indistinguishable from a real answer. Roughly a third of rows came back
    # that way. There is no sensible default for "how many calories".
    calories: float = Field(..., description="Calories in ONE serving, kcal")
    protein_g: float = Field(..., description="Protein in ONE serving, grams")
    carbs_g: float = Field(..., description="Carbohydrate in ONE serving, grams")
    fat_g: float = Field(..., description="Fat in ONE serving, grams")
    serves: int = Field(
        0,
        description="How many people the listed quantities realistically serve, whatever the recipe claims",
    )
