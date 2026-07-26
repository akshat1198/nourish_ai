"""ingredients: carry their own diet/allergen/nutrition properties

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-25

Until now `ingredients` held only name/category/aliases, while the properties
every derivation depends on (vegetarian, vegan, allergens, per_100g, gram
weights) lived solely in seed_data/ingredients.json. That file is baked into
the backend image and the container has no source mount, so an ingredient
learned at runtime could never acquire nutrition or a vegan flag — which
blocks both generated recipes and any vocabulary growth.

The seed file stays the bootstrap for a fresh install; the table becomes the
live vocabulary. Backfills all existing rows from the file in the same
migration, so derivation reads identical values before and after.
"""
import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

SEED = Path(__file__).resolve().parents[2] / "seed_data" / "ingredients.json"


def upgrade() -> None:
    op.add_column("ingredients", sa.Column("vegetarian", sa.Boolean, nullable=True))
    op.add_column("ingredients", sa.Column("vegan", sa.Boolean, nullable=True))
    op.add_column(
        "ingredients",
        sa.Column("allergens", postgresql.ARRAY(sa.Text), server_default="{}"),
    )
    op.add_column("ingredients", sa.Column("per_100g", postgresql.JSONB, nullable=True))
    op.add_column("ingredients", sa.Column("default_unit", sa.Text, nullable=True))
    op.add_column(
        "ingredients", sa.Column("grams_per_unit", sa.Numeric(10, 3), nullable=True)
    )
    # What one bare, unit-less quantity weighs — a piece for countable things, a
    # cup for bulk. Distinct from grams_per_unit, which is per default_unit and
    # is 1 for everything stored in grams.
    op.add_column(
        "ingredients", sa.Column("grams_per_piece", sa.Numeric(10, 3), nullable=True)
    )

    if not SEED.exists():  # image without seed_data: columns exist, backfill later
        return
    conn = op.get_bind()
    stmt = sa.text(
        """
        UPDATE ingredients SET
            vegetarian = :vegetarian, vegan = :vegan, allergens = :allergens,
            per_100g = CAST(:per_100g AS jsonb), default_unit = :default_unit,
            grams_per_unit = :grams_per_unit, grams_per_piece = :grams_per_piece
        WHERE name = :name
        """
    )
    for item in json.loads(SEED.read_text()):
        conn.execute(
            stmt,
            {
                "name": item["name"],
                "vegetarian": item.get("vegetarian"),
                "vegan": item.get("vegan"),
                "allergens": item.get("allergens") or [],
                "per_100g": json.dumps(item.get("per_100g") or {}),
                "default_unit": item.get("default_unit"),
                "grams_per_unit": item.get("grams_per_unit"),
                "grams_per_piece": item.get("grams_per_piece"),
            },
        )


def downgrade() -> None:
    for column in (
        "grams_per_piece", "grams_per_unit", "default_unit",
        "per_100g", "allergens", "vegan", "vegetarian",
    ):
        op.drop_column("ingredients", column)
