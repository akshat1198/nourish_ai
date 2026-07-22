"""events: online analytics + A/B capture (Stage 13)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-22

Additive, append-only event log. `variant` is null until Stage 13.2 wires
deterministic A/B assignment; `recipe_id` is null for events that aren't
recipe-scoped (e.g. results_shown). CI seeds only the 144 baseline, so DB
tests discover recipe ids dynamically — this table starts empty.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_key", sa.Text, nullable=True),
        sa.Column("session_id", sa.Text, nullable=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column(
            "recipe_id",
            sa.Integer,
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("variant", sa.Text, nullable=True),
        sa.Column("props", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_events_name_created", "events", ["name", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_events_name_created", table_name="events")
    op.drop_table("events")
