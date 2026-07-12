from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    # Display copy of ingredients: [{name, qty, unit, essential}].
    # Matching NEVER runs on this — it runs on recipe_ingredients.
    ingredients: Mapped[list] = mapped_column(JSONB)
    steps: Mapped[list[str]] = mapped_column(ARRAY(Text))
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    diet_labels: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    allergens: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    time_minutes: Mapped[int] = mapped_column(Integer)
    servings: Mapped[int] = mapped_column(Integer, default=2)
    # {calories, protein_g, carbs_g, fat_g} per serving
    nutrition: Mapped[dict] = mapped_column(JSONB, default=dict)
    # title + ingredient names + tags; FTS now, embedding input in Stage 2
    search_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    recipe_ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeIngredient(Base):
    """Join table recipes <-> canonical ingredients; pantry matching runs here."""

    __tablename__ = "recipe_ingredients"

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    qty: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)
    unit: Mapped[str] = mapped_column(Text, nullable=True)
    essential: Mapped[bool] = mapped_column(Boolean, default=True)

    recipe: Mapped["Recipe"] = relationship(back_populates="recipe_ingredients")
