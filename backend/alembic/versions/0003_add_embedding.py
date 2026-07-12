"""Add recipes.embedding vector(384) + HNSW cosine index

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

EMBED_DIM = 384


def upgrade() -> None:
    op.add_column("recipes", sa.Column("embedding", Vector(EMBED_DIM), nullable=True))
    # HNSW index for cosine distance (<=>). Query vectors are normalized, so
    # cosine and inner product agree; cosine is the explicit, safe choice.
    op.execute(
        "CREATE INDEX ix_recipes_embedding_hnsw ON recipes "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_recipes_embedding_hnsw")
    op.drop_column("recipes", "embedding")
