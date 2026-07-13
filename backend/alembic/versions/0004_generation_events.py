"""generation_events: per-agent-run audit trail

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_key", sa.Text, nullable=True),
        sa.Column("prompt_version", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("violations", JSONB, nullable=False, server_default="[]"),
        sa.Column("repaired", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("degraded", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("generation_events")
