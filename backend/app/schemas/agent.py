"""Agent request/response schemas (Stage 3.2)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    pantry: list[str] = Field(default_factory=list)
    pantry_text: Optional[str] = None
    user_key: Optional[str] = Field(None, description="Opaque client key (used by memory in 3.4)")
    question: Optional[str] = Field(None, description="e.g. 'something high-protein tonight, no dairy'")
    diet: Optional[str] = None
    exclude_allergens: list[str] = Field(default_factory=list)
    max_time_minutes: Optional[int] = None
    limit: int = Field(3, ge=1, le=10)


class MealPlanItem(BaseModel):
    recipe_id: int
    title: str
    why: str = Field(description="Why this recipe fits the request")


class MealPlanResponse(BaseModel):
    recipes: list[MealPlanItem]
    summary: str = Field(description="One or two sentences tying the plan together")


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
    error: Optional[str] = None
