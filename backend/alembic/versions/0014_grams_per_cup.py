"""ingredients: separate cup weight from piece weight

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-25

grams_per_piece was doing two incompatible jobs: the weight of one bare unit
("10 peanuts") and the weight of one cup ("1 cup peanuts"). Bulk items were
given their cup weight, so a recipe calling for 10 peanuts resolved to ten
CUPS — 1,460 g, 8,278 kcal, and a stuffed bitter gourd reporting 2,381 kcal
per serving.

The two are now separate columns. grams_per_piece means one piece; where a
bare number genuinely means a cup (rice, flour), the two are equal.
"""
import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

SEED = Path(__file__).resolve().parents[2] / "seed_data" / "ingredients.json"


def upgrade() -> None:
    op.add_column(
        "ingredients", sa.Column("grams_per_cup", sa.Numeric(10, 3), nullable=True)
    )
    if not SEED.exists():
        return
    conn = op.get_bind()
    stmt = sa.text(
        "UPDATE ingredients SET grams_per_cup = :cup, grams_per_piece = :piece "
        "WHERE name = :name"
    )
    for item in json.loads(SEED.read_text()):
        conn.execute(
            stmt,
            {
                "name": item["name"],
                "cup": item.get("grams_per_cup"),
                "piece": item.get("grams_per_piece"),
            },
        )


def downgrade() -> None:
    op.drop_column("ingredients", "grams_per_cup")
