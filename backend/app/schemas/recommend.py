"""Request/response schemas for recipe recommendations."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.allergens import normalize_request_allergens


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
    disliked_ingredients: list[str] = Field(
        default_factory=list,
        description="Soft preference: recipes containing these are demoted (not excluded)",
    )
    cuisines: list[str] = Field(
        default_factory=list,
        description="Taxonomy ids (OR): 'indian' (any region) or 'indian/gujarati'",
    )
    meal_type: Optional[str] = Field(
        None, description="breakfast | lunch | dinner | snack | dessert"
    )
    nutrition_goals: list[str] = Field(
        default_factory=list,
        description="AND: high_protein | low_calorie | low_fat | low_carb (per-serving thresholds)",
    )
    limit: int = Field(10, ge=1, le=50)
    session_id: Optional[str] = Field(
        None, description="Persisted per-browser session id, used for A/B bucketing"
    )

    @field_validator("exclude_allergens")
    @classmethod
    def _canonicalize_allergens(cls, v: list[str]) -> list[str]:
        # Remap token variants (egg->eggs) so the exact-overlap filter can't miss;
        # unknown tokens pass through (a filter no-op, never a silent safety drop).
        return normalize_request_allergens(v)


class IngredientMatch(BaseModel):
    name: str
    essential: bool


class RecipeCandidate(BaseModel):
    """A retrieved recipe with match stats."""

    id: int
    title: str
    diet_labels: list[str]
    allergens: list[str]
    tags: list[str]
    cuisine: Optional[str] = None
    region: Optional[str] = None
    meal_types: list[str] = Field(default_factory=list)
    nutrition: dict
    matched_ingredients: list[str]
    missing_ingredients: list[str]
    matched_essential: int
    total_essential: int
    # Provenance, so the UI can be honest about where a recipe came from:
    # "generated" recipes were written for a request, and nutrition here is
    # always estimated from ingredients rather than measured.
    source: str = "seed"
    nutrition_estimated: bool = False

    # Category-weighted match stats. Retrieval fills these in (it is where
    # ingredient categories are known); ranking prefers them and falls back to
    # raw counts when absent, so a hand-built candidate still scores sensibly.
    matched_weight: Optional[float] = None
    missing_weight: Optional[float] = None
    matched_essential_weight: Optional[float] = None
    total_essential_weight: Optional[float] = None
    # Missing ingredients that actually block cooking (weight >= the substantive
    # cutoff) — missing cumin doesn't, missing the chicken does.
    missing_substantive: int = 0


class SubstitutionSuggestion(BaseModel):
    missing: str  # essential ingredient the recipe needs and pantry lacks
    use: str  # pantry ingredient that can substitute for it
    ratio: str


class RankedRecipe(RecipeCandidate):
    """A candidate with a computed relevance score and a human explanation."""

    score: float
    why: str
    substitutions: list[SubstitutionSuggestion] = Field(default_factory=list)
    # Soft filters (meal type / time / nutrition goals) this recipe satisfies,
    # out of those requested. Drives the strict ordering and the UI grouping.
    filters_matched: int = 0
    filters_requested: int = 0
    # False only on off-cuisine results, which the UI must show under an explicit
    # divider rather than blending into the main list.
    cuisine_matched: bool = True
    # No substantive ingredient missing — cookable from the pantry as-is.
    pantry_complete: bool = False
    # Grades within the passing set: more protein / fewer carbs ranks higher.
    # 0.0 when no nutrition goal was requested.
    nutrition_fit: float = 0.0


class RecommendResponse(BaseModel):
    results: list[RankedRecipe]
    mode: str = Field(
        "normal",
        description=(
            "normal | substitution_first | shopping_assisted (low-confidence "
            "fallback) | off_cuisine (too few recipes in the requested cuisine, "
            "so results from other cuisines are appended below a divider — they "
            "carry cuisine_matched=False and never outrank an in-cuisine result)"
        ),
    )
    explanation: Optional[str] = None
    unmatched_pantry: list[str] = Field(
        default_factory=list, description="Pantry names that resolved to no ingredient"
    )
    variant: Optional[str] = Field(
        None, description="A/B variant this response was generated under, if session_id was supplied"
    )
