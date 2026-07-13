"""agent_traces

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_traces",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("engine", sa.Text, nullable=False),  # single | graph
        sa.Column("seq", sa.Integer, nullable=False, server_default="0"),
        sa.Column("node", sa.Text, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_agent_traces_session_id", "agent_traces", ["session_id"])


def downgrade() -> None:
    op.drop_table("agent_traces")
