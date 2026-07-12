"""Backfill recipes.embedding from search_text (Stage 2.1).

Idempotent: pass --all to re-embed everything, otherwise only rows with a
null embedding are processed. Run after `alembic upgrade head`.

Run:  python scripts/embed_recipes.py         (from backend/)
      python scripts/embed_recipes.py --all
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Recipe  # noqa: E402
from app.services.embedder import get_embedder  # noqa: E402

BATCH = 64


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="re-embed all recipes")
    args = ap.parse_args()

    embedder = get_embedder()
    with SessionLocal() as session:
        query = select(Recipe)
        if not args.all:
            query = query.where(Recipe.embedding.is_(None))
        recipes = session.execute(query).scalars().all()

        if not recipes:
            print("Nothing to embed (all recipes already have embeddings).")
            return

        total = len(recipes)
        for start in range(0, total, BATCH):
            chunk = recipes[start : start + BATCH]
            vectors = embedder.embed([r.search_text for r in chunk])
            for recipe, vector in zip(chunk, vectors):
                recipe.embedding = vector
            session.commit()
            print(f"  embedded {min(start + BATCH, total)}/{total}")

    print(f"Done. {total}/{total} embedded (dim={embedder.dim}).")


if __name__ == "__main__":
    main()
