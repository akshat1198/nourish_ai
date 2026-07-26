"""Saved recipes + meal plan schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RecipeSummary(BaseModel):
    """Compact card shape for saved lists and plan items (no derivation cost)."""

    id: int
    title: str
    cuisine: Optional[str] = None
    region: Optional[str] = None
    image_url: Optional[str] = None


class SavedListOut(BaseModel):
    recipes: list[RecipeSummary] = Field(default_factory=list)


class SaveIn(BaseModel):
    recipe_id: int


class PlanCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class PlanItemIn(BaseModel):
    recipe_id: int
    slot: Optional[str] = Field(None, max_length=120)


class PlanItemOut(BaseModel):
    recipe: RecipeSummary
    slot: Optional[str] = None


class PlanOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    items: list[PlanItemOut] = Field(default_factory=list)


class PlanSummaryOut(BaseModel):
    id: int
    name: str
    item_count: int
    created_at: datetime


class PlanListOut(BaseModel):
    plans: list[PlanSummaryOut] = Field(default_factory=list)
