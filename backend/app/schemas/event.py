"""Online analytics event schemas (Stage 13)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    name: str
    session_id: Optional[str] = None
    recipe_id: Optional[int] = None
    variant: Optional[str] = None
    props: dict = Field(default_factory=dict)


class VariantStat(BaseModel):
    variant: str
    count: int
    by_name: dict[str, int] = Field(default_factory=dict)


class ExperimentSummaryOut(BaseModel):
    experiment: str
    total: int
    variants: list[VariantStat] = Field(default_factory=list)
