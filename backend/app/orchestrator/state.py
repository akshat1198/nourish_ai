"""Shared graph state."""
from __future__ import annotations

from typing import TypedDict


class PlanState(TypedDict, total=False):
    request: dict  # AgentRequest.model_dump()
    pantry: list  # normalized pantry after pantry_analyst
    candidates: list  # recipes from search_recipes
    draft: dict  # DraftPlan.model_dump() — the current recipe picks
    violations: list  # from safety_nutritionist (drives the repair edge)
    nutrition: list  # per-recipe nutrition
    shopping_list: dict
    summary: str  # supervisor's synthesis
    degraded: bool  # violations survived the repair budget
    repair_count: int
    trace: list  # ordered node events (groundwork for trace reads)
