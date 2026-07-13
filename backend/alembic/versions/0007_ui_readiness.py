"""ui readiness: pantry staples, profile identity, recipe cuisine/region/meal_types

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Persistent pantry gains a "staple" flag (always-on-hand items).
    op.add_column(
        "pantry_items",
        sa.Column("is_staple", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    # Profiles gain identity fields populated from the Google token.
    op.add_column("user_profiles", sa.Column("email", sa.Text, nullable=True))
    op.add_column("user_profiles", sa.Column("name", sa.Text, nullable=True))

    # Recipes gain a normalized cuisine taxonomy + meal types for filtering.
    op.add_column("recipes", sa.Column("cuisine", sa.Text, nullable=True))
    op.add_column("recipes", sa.Column("region", sa.Text, nullable=True))
    op.add_column(
        "recipes",
        sa.Column("meal_types", ARRAY(sa.Text), nullable=False, server_default="{}"),
    )
    op.create_index("ix_recipes_cuisine", "recipes", ["cuisine"])
    op.create_index(
        "ix_recipes_meal_types", "recipes", ["meal_types"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_recipes_meal_types", table_name="recipes")
    op.drop_index("ix_recipes_cuisine", table_name="recipes")
    op.drop_column("recipes", "meal_types")
    op.drop_column("recipes", "region")
    op.drop_column("recipes", "cuisine")
    op.drop_column("user_profiles", "name")
    op.drop_column("user_profiles", "email")
    op.drop_column("pantry_items", "is_staple")
