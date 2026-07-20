"""One-off cleanup: strip 'STEP N' marker pollution from already-imported
TheMealDB recipes.

The 6.2c import kept TheMealDB's standalone "STEP 1/2/3" delimiter lines as
their own steps and set `description` to the "step 1" marker. This surfaced on
the Stage 7.1 detail page. Reuses the (now idempotent) `clean_steps` parser, so
re-running the importer would produce the same result — this just avoids a full
708-recipe re-fetch. Safe to re-run: embeddings are built from `search_text`
(title + ingredients + tags), never steps, so no re-embed is needed.

Run from backend/ (DB must be up):
  ../.venv/bin/python -m scripts.ingest.clean_themealdb
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db import SessionLocal  # noqa: E402
from app.models import Recipe  # noqa: E402
from scripts.ingest.themealdb import clean_steps  # noqa: E402


def main() -> None:
    with SessionLocal() as session:
        rows = (
            session.execute(select(Recipe).where(Recipe.source == "themealdb"))
            .scalars()
            .all()
        )
        steps_fixed = 0
        desc_fixed = 0
        for r in rows:
            new_steps = clean_steps(r.steps or [])
            if new_steps and new_steps != (r.steps or []):
                r.steps = new_steps
                steps_fixed += 1
            # description was always a step-marker proxy; TheMealDB has none.
            if r.description:
                r.description = ""
                desc_fixed += 1
        session.commit()
        print(
            f"themealdb rows: {len(rows)} | steps cleaned: {steps_fixed} "
            f"| descriptions cleared: {desc_fixed}"
        )


if __name__ == "__main__":
    main()
