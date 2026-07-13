"""Profile + feedback schemas (AGENT-01/02, API-05)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProfileIn(BaseModel):
    diet: Optional[str] = None
    allergens: list[str] = Field(default_factory=list)
    disliked_ingredients: list[str] = Field(default_factory=list)
    cuisine_prefs: list[str] = Field(default_factory=list)


class ProfileOut(ProfileIn):
    user_key: str


class FeedbackIn(BaseModel):
    user_key: str
    recipe_id: int
    action: Literal["recommended", "cooked", "skipped"]
