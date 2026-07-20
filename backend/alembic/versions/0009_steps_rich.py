"""recipe steps_rich: LLM-enriched method (WS6)

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-20

An optional, nullable copy of the method with prep state + cooking cues added by
a one-time LLM pass (scripts/enrich_steps.py). Additive: the original `steps`
are preserved and the detail endpoint prefers `steps_rich` only when present, so
un-enriched rows (and CI, which never runs the enrichment) are unaffected.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("steps_rich", sa.ARRAY(sa.Text), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recipes", "steps_rich")
