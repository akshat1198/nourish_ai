from typing import Optional

from sqlalchemy import Boolean, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Ingredient(Base):
    """Canonical ingredient vocabulary — the normalization spine.

    All matching happens against canonical ingredient ids; free-text names
    resolve here via `name` or `aliases` (e.g. "capsicum" -> bell pepper).

    Rows also carry the properties every derivation depends on. These used to
    live only in seed_data/ingredients.json, which is baked into the image —
    so an ingredient learned at runtime could never get nutrition or a vegan
    flag. The seed file bootstraps a fresh install; this table is the live
    vocabulary and is what `derivation.load_props` reads.
    """

    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, index=True)
    category: Mapped[str] = mapped_column(Text)  # protein/vegetable/dairy/grain/pantry/...
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    vegetarian: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    vegan: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    allergens: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    # {calories, protein_g, carbs_g, fat_g} per 100 g
    per_100g: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    default_unit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # grams per `default_unit`; 1 for anything stored in grams.
    grams_per_unit: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), nullable=True)
    # What ONE piece weighs — distinct from the cup weight, which for anything
    # countable differs by orders of magnitude (a peanut 0.5 g, a cup 146 g).
    grams_per_piece: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), nullable=True)
    grams_per_cup: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), nullable=True)
