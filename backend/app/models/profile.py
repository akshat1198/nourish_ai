from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserProfile(Base):
    """Per-user preferences. `user_key` is an opaque client key."""

    __tablename__ = "user_profiles"

    user_key: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=True)  # from the Google token
    name: Mapped[str] = mapped_column(Text, nullable=True)
    diet: Mapped[str] = mapped_column(Text, nullable=True)
    allergens: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    disliked_ingredients: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    cuisine_prefs: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InteractionHistory(Base):
    """Recency memory: what was recommended / cooked / skipped, when."""

    __tablename__ = "interaction_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(Text, index=True)
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE")
    )
    # append-only log; recommended | cooked | uncooked | liked | disliked | unrated
    action: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
