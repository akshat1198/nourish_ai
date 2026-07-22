"""recipe provenance: source, source_url, attribution, image_url, license, nutrition_estimated

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-14

Own-the-data ingestion needs to record where each recipe came from
and how it may be used. `source` defaults to 'seed' so the existing 144 curated
rows are tagged automatically. A PARTIAL unique index on (source, source_url)
guards against re-importing the same URL from the same source, while allowing
the many seed rows whose source_url is NULL (NULLs would otherwise be treated
as distinct, but the partial predicate makes the intent explicit).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Provenance: where the recipe came from and how it may be used.
    op.add_column(
        "recipes",
        sa.Column("source", sa.Text, nullable=False, server_default="seed"),
    )
    op.add_column("recipes", sa.Column("source_url", sa.Text, nullable=True))
    op.add_column("recipes", sa.Column("attribution", sa.Text, nullable=True))
    op.add_column("recipes", sa.Column("image_url", sa.Text, nullable=True))
    op.add_column("recipes", sa.Column("license_note", sa.Text, nullable=True))
    # Archana's corpus lacks nutrition; when we estimate it from canonical
    # ingredients we flag it so the UI can be honest (and empty otherwise).
    op.add_column(
        "recipes",
        sa.Column(
            "nutrition_estimated",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # No double-imports of the same URL from the same source. Partial: seed rows
    # (source_url IS NULL) are exempt.
    op.create_index(
        "ux_recipes_source_source_url",
        "recipes",
        ["source", "source_url"],
        unique=True,
        postgresql_where=sa.text("source_url IS NOT NULL"),
    )
    op.create_index("ix_recipes_source", "recipes", ["source"])


def downgrade() -> None:
    op.drop_index("ix_recipes_source", table_name="recipes")
    op.drop_index("ux_recipes_source_source_url", table_name="recipes")
    op.drop_column("recipes", "nutrition_estimated")
    op.drop_column("recipes", "license_note")
    op.drop_column("recipes", "image_url")
    op.drop_column("recipes", "attribution")
    op.drop_column("recipes", "source_url")
    op.drop_column("recipes", "source")
