"""Domain schema: recipes, ingredients, join table, substitutions, pantry

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingredients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("aliases", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.UniqueConstraint("name", name="uq_ingredients_name"),
    )
    op.create_index("ix_ingredients_name", "ingredients", ["name"])

    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("ingredients", JSONB, nullable=False),
        sa.Column("steps", ARRAY(sa.Text), nullable=False),
        sa.Column("tags", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("diet_labels", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("allergens", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("time_minutes", sa.Integer, nullable=False),
        sa.Column("servings", sa.Integer, nullable=False, server_default="2"),
        sa.Column("nutrition", JSONB, nullable=False, server_default="{}"),
        sa.Column("search_text", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_recipes_tags", "recipes", ["tags"], postgresql_using="gin")
    op.create_index(
        "ix_recipes_diet_labels", "recipes", ["diet_labels"], postgresql_using="gin"
    )
    op.create_index(
        "ix_recipes_allergens", "recipes", ["allergens"], postgresql_using="gin"
    )
    op.execute(
        "CREATE INDEX ix_recipes_search_text_fts ON recipes "
        "USING gin (to_tsvector('english', search_text))"
    )

    op.create_table(
        "recipe_ingredients",
        sa.Column(
            "recipe_id",
            sa.Integer,
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "ingredient_id",
            sa.Integer,
            sa.ForeignKey("ingredients.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("qty", sa.Numeric(8, 2), nullable=True),
        sa.Column("unit", sa.Text, nullable=True),
        sa.Column("essential", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index(
        "ix_recipe_ingredients_ingredient_id", "recipe_ingredients", ["ingredient_id"]
    )

    op.create_table(
        "substitutions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "ingredient_id",
            sa.Integer,
            sa.ForeignKey("ingredients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "substitute_id",
            sa.Integer,
            sa.ForeignKey("ingredients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ratio", sa.Text, nullable=False, server_default="1:1"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.8"),
        sa.Column("diet_ok", ARRAY(sa.Text), nullable=False, server_default="{}"),
    )
    op.create_index("ix_substitutions_ingredient_id", "substitutions", ["ingredient_id"])

    op.create_table(
        "pantry_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_key", sa.Text, nullable=False),
        sa.Column(
            "ingredient_id",
            sa.Integer,
            sa.ForeignKey("ingredients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("qty", sa.Numeric(8, 2), nullable=True),
        sa.Column("unit", sa.Text, nullable=True),
        sa.Column("expires_on", sa.Date, nullable=True),
    )
    op.create_index("ix_pantry_items_user_key", "pantry_items", ["user_key"])


def downgrade() -> None:
    op.drop_table("pantry_items")
    op.drop_table("substitutions")
    op.drop_table("recipe_ingredients")
    op.drop_table("recipes")
    op.drop_table("ingredients")
