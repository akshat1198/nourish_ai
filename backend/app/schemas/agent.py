"""Agent request/response schemas (Stage 3.2)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    pantry: list[str] = Field(default_factory=list)
    pantry_text: Optional[str] = None
    session_id: Optional[str] = Field(
        None, description="Continues a checkpointed orchestrator session (multi-turn refinement)"
    )
    user_key: Optional[str] = Field(None, description="Opaque client key (used by memory in 3.4)")
    question: Optional[str] = Field(None, description="e.g. 'something high-protein tonight, no dairy'")
    diet: Optional[str] = None
    exclude_allergens: list[str] = Field(default_factory=list)
    disliked_ingredients: list[str] = Field(default_factory=list)
    cuisine_prefs: list[str] = Field(default_factory=list)
    max_time_minutes: Optional[int] = None
    limit: int = Field(3, ge=1, le=10)


class MealPlanItem(BaseModel):
    recipe_id: int
    title: str
    why: str = Field(description="Why this recipe fits the request")


class MealPlanResponse(BaseModel):
    recipes: list[MealPlanItem]
    summary: str = Field(description="One or two sentences tying the plan together")


class DraftPlan(BaseModel):
    """recipe_planner's structured output (recipes only; supervisor adds the summary)."""

    recipes: list[MealPlanItem]


class OrchestrateResponse(BaseModel):
    plan: Optional[MealPlanResponse] = None
    degraded: bool = False
    violations: list[dict] = Field(default_factory=list)
    nutrition: list[dict] = Field(default_factory=list)
    shopping_list: dict = Field(default_factory=dict)
    repair_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    trace: list[dict] = Field(default_factory=list)


class AgentResult(BaseModel):
    plan: Optional[MealPlanResponse] = None
    degraded: bool = Field(
        False, description="True when a validated agent plan couldn't be produced (fell back)"
    )
    repaired: bool = Field(False, description="True if a repair turn was needed")
    violations: list[dict] = Field(
        default_factory=list, description="Unresolved constraint violations (empty when clean)"
    )
    stop_reason: str
    iterations: int
    tool_calls: int
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None
