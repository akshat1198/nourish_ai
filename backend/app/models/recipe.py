from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

EMBED_DIM = 384


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    # Display copy of ingredients: [{name, qty, unit, essential}].
    # Matching NEVER runs on this — it runs on recipe_ingredients.
    ingredients: Mapped[list] = mapped_column(JSONB)
    steps: Mapped[list[str]] = mapped_column(ARRAY(Text))
    # LLM-enriched method (WS6): prep state + cooking cues. Nullable; the detail
    # endpoint prefers it when present, else falls back to `steps`.
    steps_rich: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    diet_labels: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    allergens: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    # Normalized cuisine taxonomy (Stage 5): cuisine="indian", region="gujarati";
    # region is NULL when the source has no sub-cuisine. meal_types ⊆
    # {breakfast,lunch,dinner,snack,dessert}.
    cuisine: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meal_types: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    time_minutes: Mapped[int] = mapped_column(Integer)
    servings: Mapped[int] = mapped_column(Integer, default=2)
    # {calories, protein_g, carbs_g, fat_g} per serving
    nutrition: Mapped[dict] = mapped_column(JSONB, default=dict)
    # title + ingredient names + tags; FTS now, embedding input in Stage 2
    search_text: Mapped[str] = mapped_column(Text)
    # Dense embedding of search_text (Stage 2.1); null until backfilled.
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(EMBED_DIM), nullable=True
    )
    # Provenance (Stage 6): where the recipe came from + how it may be used.
    # source ∈ {seed, themealdb, archanas}; the 144 curated rows are
    # "seed". source_url/attribution/image_url/license_note come from ingestion.
    source: Mapped[str] = mapped_column(Text, default="seed", server_default="seed")
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attribution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    license_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # True when nutrition was estimated from ingredients (Archana's has none),
    # so the UI can show it honestly or hide it.
    nutrition_estimated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=func.false()
    )
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
