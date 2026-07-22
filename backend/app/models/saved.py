from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SavedRecipe(Base):
    """A recipe a user bookmarked. Unique per (user, recipe)."""

    __tablename__ = "saved_recipes"
    __table_args__ = (UniqueConstraint("user_key", "recipe_id", name="uq_saved_user_recipe"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(Text, index=True)
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MealPlan(Base):
    """A named collection of recipes to cook."""

    __tablename__ = "meal_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(Text, index=True)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MealPlanItem(Base):
    """A recipe placed in a plan under a free-text slot (e.g. "Mon dinner").

    One appearance per recipe per plan (unique); `slot` is just a label.
    """

    __tablename__ = "meal_plan_items"
    __table_args__ = (
        UniqueConstraint("plan_id", "recipe_id", name="uq_plan_recipe"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meal_plans.id", ondelete="CASCADE"), index=True
    )
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE")
    )
    slot: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
