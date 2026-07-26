"""recipes.time_minutes: no longer required

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-25

Cooking time is no longer filtered on, ranked by, or displayed. The column is
kept rather than dropped — the imported values are real source data and this
stays reversible — but it no longer has to be supplied, so a written recipe
doesn't have to invent a number nobody reads.
"""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("recipes", "time_minutes", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Anything written since the upgrade may have no time; give those a value
    # so the NOT NULL can be restored.
    op.execute("UPDATE recipes SET time_minutes = 30 WHERE time_minutes IS NULL")
    op.alter_column("recipes", "time_minutes", existing_type=sa.Integer(), nullable=False)
