"""Enable pgvector extension

Revision ID: 0001
Revises:
Create Date: 2026-07-12

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # POSTGRES_USER is superuser in the pgvector/pgvector image, so this
    # works from a migration — no init-script dependency.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
