"""Agent eval — constraint pass-rate (Stage 3.5).

Replays gold cases through the real agent and reports:
  * constraint pass-rate  — plan validator-clean on the FIRST attempt (no repair)
  * repair-success rate   — of runs that needed repair, how many got fixed
  * degraded rate         — fell back to the deterministic plan
  * final-clean           — final output clean (should be 1.0 by construction)
  * mean tool calls, p50 latency, tokens, estimated $ cost

⚠️ This hits the real Anthropic API and spends tokens. It is capped at 30 cases
and requires --yes for more than 3 (so a full run is always deliberate). Do a
small run first (default 2) to project the full cost.

Baseline (2026-07-13, sonnet-5, 30 cases): constraint pass-rate 1.00 (30/30),
0 degraded, 1.6 mean tool calls, p50 15.3s, ~$1.02. NOTE: a perfect score
reflects an easy gold set (structured queries, clear-cut constraints) — the
repair/fallback path never fired here; it's proven by unit tests. Adversarial /
conflicting-constraint cases would exercise it and lower the pass-rate.

Run:  python -m app.evals.run_agent                 # 2-case dry run
      python -m app.evals.run_agent --limit 30 --yes # full run
"""
from __future__ import annotations

import argparse
import statistics
import time

from app.agent.loop import run_agent
from app.core.config import settings
from app.db import SessionLocal
from app.evals.common import load_cases
from app.llm.client import get_llm, is_enabled
from app.schemas.agent import AgentRequest

MAX_CASES = 30
# Claude Sonnet 5 standard pricing ($/1M tokens); intro rates are lower, so this
# is a conservative (over-)estimate.
COST_IN_PER_1M = 3.0
COST_OUT_PER_1M = 15.0


def _cost(tin: int, tout: int) -> float:
    return tin / 1_000_000 * COST_IN_PER_1M + tout / 1_000_000 * COST_OUT_PER_1M


def run(limit: int, verbose: bool) -> None:
    client = get_llm().raw()
    rows = []
    with SessionLocal() as session:
        cases = load_cases()[:limit]
        for case in cases:
            req = AgentRequest(
                pantry=case.pantry,
                diet=case.diet,
                exclude_allergens=case.exclude_allergens,
                max_time_minutes=case.max_time_minutes,
                limit=2,
            )
            t0 = time.perf_counter()
            result = run_agent(session, req, client=client)
            wall = time.perf_counter() - t0
            rows.append((case, result, wall))
            if verbose:
                flag = "clean" if (not result.repaired and not result.degraded) else (
                    "degraded" if result.degraded else "repaired"
                )
                top = result.plan.recipes[0].title if result.plan and result.plan.recipes else "(none)"
                print(f"  [{flag:8}] {case.name:40} top: {top}  ({wall:.0f}s)")

    n = len(rows)
    if not n:
        print("no cases")
        return

    clean_first = sum(1 for _, r, _ in rows if not r.repaired and not r.degraded)
    needed_repair = [r for _, r, _ in rows if r.repaired]
    repair_ok = sum(1 for r in needed_repair if not r.degraded)
    degraded = sum(1 for _, r, _ in rows if r.degraded)
    tool_calls = [r.tool_calls for _, r, _ in rows]
    latencies = sorted(w for _, _, w in rows)
    tin = sum(r.input_tokens for _, r, _ in rows)
    tout = sum(r.output_tokens for _, r, _ in rows)

    print("\n" + "=" * 60)
    print(f"  Agent eval — {n} cases, model={settings.LLM_MODEL_MAIN}")
    print("=" * 60)
    print(f"  constraint pass-rate (clean 1st try) : {clean_first / n:.2f}  ({clean_first}/{n})")
    if needed_repair:
        print(f"  repair-success rate                  : {repair_ok / len(needed_repair):.2f}  ({repair_ok}/{len(needed_repair)})")
    else:
        print("  repair-success rate                  : n/a (no repairs needed)")
    print(f"  degraded rate                        : {degraded / n:.2f}  ({degraded}/{n})")
    print(f"  mean tool calls                      : {statistics.mean(tool_calls):.1f}")
    print(f"  p50 latency                          : {statistics.median(latencies):.1f}s")
    print(f"  tokens                               : {tin:,} in / {tout:,} out")
    print(f"  estimated cost                       : ${_cost(tin, tout):.4f}  (@ ${COST_IN_PER_1M}/${COST_OUT_PER_1M} per 1M)")
    print(f"  projected 30-case cost               : ${_cost(tin, tout) / n * 30:.4f}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=2)
    ap.add_argument("--yes", action="store_true", help="required for more than 3 cases")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if not is_enabled():
        raise SystemExit("ANTHROPIC_API_KEY not set — the agent eval needs the real API.")

    limit = min(args.limit, MAX_CASES)
    if limit > 3 and not args.yes:
        raise SystemExit(
            f"About to run {limit} agent cases against the REAL API (spends tokens).\n"
            f"Re-run with --yes to confirm, or use a smaller --limit for a dry run."
        )
    run(limit, args.verbose)


if __name__ == "__main__":
    main()
