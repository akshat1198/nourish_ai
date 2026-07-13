"""Fallback-trigger eval (RETR-05).

Runs sparse / awkward pantries through retrieve -> rank -> apply_fallback and
reports how often (and into which mode) the low-confidence fallback fires.
Uses the SQL path so it needs no LLM or embedder.

Run:  python -m app.evals.run_fallback   (from backend/)
"""
from __future__ import annotations

from app.db import SessionLocal
from app.services.fallback import apply_fallback
from app.services.ingredients import resolve_pantry
from app.services.ranking import rank
from app.services.retrieval import fetch_candidates

# Sparse or mismatched pantries — each should NOT get a confident normal answer.
SPARSE = [
    ["water"],
    ["salt", "black pepper"],
    ["tofu"],  # single protein; substitution territory
    ["lettuce"],
    ["ginger", "garlic"],
]


def main():
    with SessionLocal() as session:
        rows = []
        triggered = 0
        for pantry in SPARSE:
            resolved = resolve_pantry(session, pantry)
            ranked = rank(fetch_candidates(session, resolved.ingredient_ids, limit=50), limit=5)
            mode, _expl, _out = apply_fallback(session, ranked, resolved.ingredient_ids)
            if mode != "normal":
                triggered += 1
            rows.append((pantry, mode, ranked[0].title if ranked else "(none)"))

    print("\n" + "=" * 60)
    print("  Fallback eval — sparse pantries")
    print("=" * 60)
    for pantry, mode, top in rows:
        print(f"  {str(pantry):32} -> {mode:18} top: {top}")
    rate = triggered / len(SPARSE)
    print(f"\n  fallback-trigger rate: {triggered}/{len(SPARSE)} = {rate:.2f}\n")


if __name__ == "__main__":
    main()
