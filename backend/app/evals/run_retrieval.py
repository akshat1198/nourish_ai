"""Retrieval eval harness v0 (Stage 1.5).

Runs the recommendation pipeline (resolve -> retrieve -> rank) over the
hand-vetted gold set and reports hit@5, hit@10, MRR and the number of
hard-constraint violations in returned results. The SQL path enforces
diet/allergen/time filters, so constraint_violations MUST be 0 — a nonzero
value is a retrieval bug, not a ranking miss.

Baseline (144-recipe corpus, RANKING_VERSION=v1, mode=sql):
    hit@5 = 1.0   hit@10 = 1.0   MRR = 1.0   constraint_violations = 0

Run:  python -m app.evals.run_retrieval   (from backend/)
      python -m app.evals.run_retrieval --mode sql --verbose
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from app.db import SessionLocal
from app.evals.common import Metrics, count_violations, load_cases, title_id_map
from app.models import Recipe
from app.services.ingredients import resolve_pantry
from app.services.ranking import rank
from app.services.retrieval import fetch_candidates

CANDIDATE_POOL = 50
TOP_K = 10


def run(mode: str = "sql", verbose: bool = False) -> Metrics:
    if mode != "sql":
        raise SystemExit(
            f"mode '{mode}' not available yet — hybrid arrives in Stage 2."
        )

    metrics = Metrics()
    with SessionLocal() as session:
        titles = title_id_map(session)
        cases = load_cases()
        for case in cases:
            relevant_ids = set()
            for t in case.relevant_titles:
                if t in titles:
                    relevant_ids.add(titles[t])
                else:
                    metrics.missing_gold.append(f"{case.name}: {t!r}")

            resolved = resolve_pantry(session, case.pantry)
            candidates = fetch_candidates(
                session,
                resolved.ingredient_ids,
                diet=case.diet,
                exclude_allergens=case.exclude_allergens,
                max_time=case.max_time_minutes,
                limit=CANDIDATE_POOL,
            )
            ranked = rank(candidates, limit=TOP_K)
            ranked_ids = [r.id for r in ranked]
            metrics.add_case(ranked_ids, relevant_ids)

            # constraint check against the full recipe rows
            id_to_recipe = {
                r.id: r
                for r in session.execute(
                    select(Recipe).where(Recipe.id.in_(ranked_ids))
                ).scalars()
            }
            for rid in ranked_ids:
                metrics.constraint_violations += count_violations(
                    id_to_recipe[rid], case
                )

            if verbose:
                hit = "✓" if relevant_ids & set(ranked_ids[:5]) else "✗"
                top = ranked[0].title if ranked else "(none)"
                print(f"  {hit} {case.name:42} top: {top}")

    return metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="sql", choices=["sql"])
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    metrics = run(mode=args.mode, verbose=args.verbose)
    summary = metrics.summary()

    print("\n" + "=" * 48)
    print(f"  Retrieval eval — mode={args.mode}")
    print("=" * 48)
    for k, v in summary.items():
        print(f"  {k:24} {v}")
    if metrics.missing_gold:
        print("\n  WARNING — unresolved gold titles (fix the eval set):")
        for m in metrics.missing_gold:
            print(f"    - {m}")
    print()


if __name__ == "__main__":
    main()
