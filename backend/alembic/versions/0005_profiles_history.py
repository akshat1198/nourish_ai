"""user_profiles + interaction_history

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_key", sa.Text, primary_key=True),
        sa.Column("diet", sa.Text, nullable=True),
        sa.Column("allergens", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column(
            "disliked_ingredients", ARRAY(sa.Text), nullable=False, server_default="{}"
        ),
        sa.Column("cuisine_prefs", ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "interaction_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_key", sa.Text, nullable=False),
        sa.Column(
            "recipe_id",
            sa.Integer,
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_interaction_history_user_key", "interaction_history", ["user_key"])
    op.create_index(
        "ix_interaction_history_created_at", "interaction_history", ["created_at"]
    )


def downgrade() -> None:
    op.drop_table("interaction_history")
    op.drop_table("user_profiles")
