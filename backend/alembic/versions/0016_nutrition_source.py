"""recipes.nutrition_source: how the stored nutrition was arrived at

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-28

`nutrition_estimated` answers whether the numbers are an estimate; it cannot say
whether they were computed from the ingredient list or guessed when that
computation produced something implausible. The UI has to tell those apart —
"we added up your ingredients, roughly" and "we could not, so we asked the
model" are different claims, and showing the second as the first would pass a
guess off as arithmetic.

Text rather than an enum, matching recipes.source: adding a value later is then
a code change rather than another migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column(
            "nutrition_source",
            sa.Text(),
            nullable=False,
            server_default="derived",
        ),
    )
    # Every existing row was derived by classify_and_derive, so the default is
    # right for all of them except those it declined to produce a value for.
    op.execute(
        "UPDATE recipes SET nutrition_source = 'none' "
        "WHERE nutrition IS NULL OR nutrition = '{}'::jsonb"
    )


def downgrade() -> None:
    op.drop_column("recipes", "nutrition_source")
