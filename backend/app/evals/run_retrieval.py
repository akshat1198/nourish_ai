"""Retrieval eval harness.

Runs the recommendation pipeline over a gold set and reports hit@5, hit@10,
MRR and hard-constraint violations. Supports the SQL path, the hybrid
(SQL+vector RRF) path, or both side by side.

The SQL and hybrid paths both enforce diet/allergen/time, so
constraint_violations MUST be 0 — a nonzero value is a retrieval bug.

Baselines — 144-recipe seed corpus (RANKING_VERSION=v1):
    structured (queries.jsonl):       sql & hybrid  hit@5=1.0   violations=0
    fuzzy (fuzzy_queries.jsonl):      sql 0.25  ->  hybrid 1.0  violations=0

Re-baseline — 7,580-recipe corpus (+708 themealdb +6,728 archanas):
    structured (queries.jsonl):       sql 1.0    hybrid 1.0   (holds at 52x scale)
    regional (queries_regional.jsonl):sql 0.875  hybrid 1.0   (hybrid finds the
                                      regional dish SQL drops, e.g. Kerala avial)
    fuzzy (fuzzy_queries.jsonl):      sql 0.125  hybrid 0.75   (hybrid still 6x
                                      SQL; drop from 1.0 is corpus competition,
                                      NOT pool size — RRF_POOL 30->200 unchanged)

Re-baseline — capped nutrition_fit + tightened plausibility ceilings (v8):
    structured (queries.jsonl):       sql 0.9    hybrid 1.0
    regional (queries_regional.jsonl):sql 1.0    hybrid 0.875
    fuzzy (fuzzy_queries.jsonl):      sql 0.25   hybrid 0.75
    Movement is one case either way on 8-40 case sets, in both directions, and
    follows from the data rather than the ranking: 3,619 recipes were re-derived
    and 423 lost their nutrition to the tighter ceilings, so any goal-filtered
    query reshuffles. violations stayed 0 throughout, which is the number that
    may never move.
    violations=0 on every set (cuisine/region/meal/diet/allergen filters hold).

Run:  python -m app.evals.run_retrieval --mode both
      python -m app.evals.run_retrieval --mode both --cases queries_regional.jsonl -v
"""
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.evals.common import (
    EVAL_DIR,
    Metrics,
    count_violations,
    load_cases,
    title_id_map,
)
from app.models import Recipe
from app.services.embedder import get_embedder
from app.services.ingredients import resolve_pantry
from app.services.ranking import annotate, rank
from app.services.retrieval import fetch_candidates, fetch_hybrid

CANDIDATE_POOL = 50
TOP_K = 10


def run(mode: str, cases_path: Path, verbose: bool = False) -> Metrics:
    metrics = Metrics()
    embedder = get_embedder() if mode == "hybrid" else None

    with SessionLocal() as session:
        titles = title_id_map(session)
        for case in load_cases(cases_path):
            relevant_ids = set()
            for t in case.relevant_titles:
                if t in titles:
                    relevant_ids.add(titles[t])
                else:
                    metrics.missing_gold.append(f"{case.name}: {t!r}")

            resolved = resolve_pantry(session, case.pantry)
            if mode == "hybrid":
                qv = embedder.embed([" ".join(case.pantry)])[0] if case.pantry else []
                candidates = fetch_hybrid(
                    session,
                    resolved.ingredient_ids,
                    qv,
                    diet=case.diet,
                    exclude_allergens=case.exclude_allergens,
                    cuisines=case.cuisines,
                    meal_type=case.meal_type,
                    limit=CANDIDATE_POOL,
                )
                ranked = annotate(candidates, limit=TOP_K)
            else:
                candidates = fetch_candidates(
                    session,
                    resolved.ingredient_ids,
                    diet=case.diet,
                    exclude_allergens=case.exclude_allergens,
                    cuisines=case.cuisines,
                    meal_type=case.meal_type,
                    limit=CANDIDATE_POOL,
                )
                ranked = rank(candidates, limit=TOP_K)

            ranked_ids = [r.id for r in ranked]
            metrics.add_case(ranked_ids, relevant_ids)

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
                hit = "hit " if relevant_ids & set(ranked_ids[:5]) else "miss"
                top = ranked[0].title if ranked else "(none)"
                print(f"  [{mode:6}] {hit} {case.name:40} top: {top}")

    return metrics


def _print(mode: str, m: Metrics):
    s = m.summary()
    print(f"  {mode:8} | hit@5={s['hit@5']:<6} hit@10={s['hit@10']:<6} "
          f"MRR={s['MRR']:<6} violations={s['constraint_violations']}")
    if m.missing_gold:
        print("    WARNING unresolved gold titles:")
        for x in m.missing_gold:
            print(f"      - {x}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="both", choices=["sql", "hybrid", "both"])
    ap.add_argument("--cases", default="queries.jsonl", help="filename under seed_data/eval/")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    cases_path = EVAL_DIR / args.cases
    modes = ["sql", "hybrid"] if args.mode == "both" else [args.mode]

    print("\n" + "=" * 60)
    print(f"  Retrieval eval — cases={args.cases}")
    print("=" * 60)
    for mode in modes:
        m = run(mode, cases_path, verbose=args.verbose)
        _print(mode, m)
    print()


if __name__ == "__main__":
    main()
