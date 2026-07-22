"""Profile + feedback schemas."""
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


# The interaction log is append-only. "cooked"/"uncooked" and
# "liked"/"disliked"/"unrated" are paired toggle events so current UI state can
# be derived latest-wins without mutating history. "recommended" is written by
# the recommend endpoint. ("saved" and "dismissed" are written elsewhere.)
FeedbackAction = Literal[
    "recommended", "cooked", "uncooked", "liked", "disliked", "unrated"
]


class FeedbackIn(BaseModel):
    user_key: str
    recipe_id: int
    action: FeedbackAction


class RecipeFeedback(BaseModel):
    """Current, derived state for one recipe (latest-wins per dimension)."""

    made: bool = False
    rating: Optional[Literal["liked", "disliked"]] = None


class FeedbackStateOut(BaseModel):
    user_key: str
    # keyed by recipe_id; only recipes with non-default state are included
    recipes: dict[int, RecipeFeedback] = Field(default_factory=dict)
