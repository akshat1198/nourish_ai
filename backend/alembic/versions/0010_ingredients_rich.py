"""recipe ingredients_rich: enriched ingredient lines (filled quantities)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-20

The lazy enrichment pass (on first view) also fills in a sensible measure
for ingredients the source left blank (many spices). The enriched ingredient
list is cached here alongside steps_rich; the detail endpoint prefers it when
present. Additive + nullable, so un-enriched rows and CI are unaffected.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("ingredients_rich", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recipes", "ingredients_rich")
