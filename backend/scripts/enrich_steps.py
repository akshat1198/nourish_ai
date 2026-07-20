"""Enrich terse recipe methods with prep state + cooking cues (WS6).

A one-time LLM pass that writes to recipes.steps_rich; the original recipes.steps
are preserved. Idempotent (skips rows already enriched unless --force), resumable
(commits per recipe, so a re-run continues where it left off), and safe (keeps
the original step count/order — a recipe is skipped if the model drifts). Run
manually, like the ingest scripts, from backend/:

  python scripts/enrich_steps.py --sample 3     # dry-run: enrich 3, print before/after
  python scripts/enrich_steps.py --limit 50      # enrich 50 un-enriched rows
  python scripts/enrich_steps.py                 # enrich everything remaining
  python scripts/enrich_steps.py --recipe-id 12279 --force
"""
import argparse
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.llm.client import LLMError, get_llm, is_enabled  # noqa: E402
from app.models import Recipe  # noqa: E402
from app.schemas.llm import EnrichedSteps  # noqa: E402

_SYSTEM = (
    "You rewrite a recipe's method to be clearer and more useful WITHOUT changing "
    "what is made. Keep the SAME number of steps in the SAME order. For each step, "
    "add the prep state of ingredients (e.g. finely diced, thinly sliced, minced) "
    "and concrete cooking cues (heat level, rough timing, and the visual/textural "
    "sign of doneness) that an experienced cook would state. Do NOT invent "
    "ingredients that aren't already implied by the recipe; do not merge, split, "
    "add, or drop steps. Keep each step to one or two sentences."
)


def _enrich(recipe: Recipe) -> Optional[list[str]]:
    """Return enriched steps, or None if there's nothing to do / the model drifted."""
    steps = recipe.steps or []
    if not steps:
        return None
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))
    ingredients = ", ".join(i.get("name", "") for i in (recipe.ingredients or []))
    prompt = (
        f"{_SYSTEM}\n\n"
        f"Title: {recipe.title}\nIngredients: {ingredients}\n"
        f"Method ({len(steps)} steps):\n{numbered}"
    )
    result = get_llm().generate_structured(
        messages=[{"role": "user", "content": prompt}],
        schema=EnrichedSteps,
        model=settings.LLM_MODEL_MAIN,
        max_tokens=2000,
    )
    out = [s.strip() for s in result.steps if s.strip()]
    if len(out) != len(steps):
        return None  # count drift — keep the original, don't store a mismatch
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="max recipes to enrich")
    ap.add_argument("--sample", type=int, default=None,
                    help="dry-run: enrich N and print before/after, write nothing")
    ap.add_argument("--recipe-id", type=int, default=None, help="only this recipe id")
    ap.add_argument("--force", action="store_true",
                    help="re-enrich rows that already have steps_rich")
    args = ap.parse_args()

    if not is_enabled():
        print("ANTHROPIC_API_KEY not set — cannot enrich.")
        sys.exit(1)

    dry = args.sample is not None
    with SessionLocal() as session:
        q = select(Recipe)
        if args.recipe_id:
            q = q.where(Recipe.id == args.recipe_id)
        elif not args.force:
            q = q.where(Recipe.steps_rich.is_(None))
        recipes = list(session.execute(q.order_by(Recipe.id)).scalars())
        cap = args.sample if dry else args.limit
        if cap is not None:
            recipes = recipes[:cap]

        print(f"{'SAMPLE (no write) — ' if dry else ''}processing {len(recipes)} recipe(s)")
        done = skipped = failed = 0
        for r in recipes:
            try:
                enriched = _enrich(r)
            except LLMError as e:
                print(f"  [{r.id}] {r.title}: LLM error — {e}")
                failed += 1
                continue
            if enriched is None:
                print(f"  [{r.id}] {r.title}: skipped (no steps or step-count drift)")
                skipped += 1
                continue
            if dry:
                print(f"\n=== [{r.id}] {r.title} ===")
                for orig, new in zip(r.steps, enriched):
                    print(f"  - {orig}\n  + {new}")
            else:
                r.steps_rich = enriched
                session.commit()  # per-recipe: resumable
                print(f"  [{r.id}] {r.title}: enriched ({len(enriched)} steps)")
            done += 1
        print(f"\nDone. {'previewed' if dry else 'enriched'}={done} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
