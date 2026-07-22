"""saved recipes + meal plans (Stage 10)

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-22

Additive per-user collections. `saved_recipes` bookmarks; `meal_plans` +
`meal_plan_items` group recipes under free-text slots for a combined shopping
list. CI seeds only the 144 baseline, so DB tests discover recipe ids
dynamically — these tables start empty.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_recipes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_key", sa.Text, nullable=False),
        sa.Column(
            "recipe_id",
            sa.Integer,
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_key", "recipe_id", name="uq_saved_user_recipe"),
    )
    op.create_index("ix_saved_recipes_user_key", "saved_recipes", ["user_key"])

    op.create_table(
        "meal_plans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_key", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_meal_plans_user_key", "meal_plans", ["user_key"])

    op.create_table(
        "meal_plan_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "plan_id",
            sa.Integer,
            sa.ForeignKey("meal_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recipe_id",
            sa.Integer,
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slot", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("plan_id", "recipe_id", name="uq_plan_recipe"),
    )
    op.create_index("ix_meal_plan_items_plan_id", "meal_plan_items", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_meal_plan_items_plan_id", table_name="meal_plan_items")
    op.drop_table("meal_plan_items")
    op.drop_index("ix_meal_plans_user_key", table_name="meal_plans")
    op.drop_table("meal_plans")
    op.drop_index("ix_saved_recipes_user_key", table_name="saved_recipes")
    op.drop_table("saved_recipes")
