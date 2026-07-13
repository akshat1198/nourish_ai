"""Agent eval — constraint pass-rate + single-vs-graph comparison (Stage 3.5 + 4.4).

Replays the gold cases through an engine and reports:
  * constraint pass-rate  — plan validator-clean on the FIRST attempt (no repair)
  * repair / degraded rate — needed a repair turn / fell back deterministically
  * mean tool calls (single only), p50 latency, tokens, estimated $ cost

Two engines, same cases (AGENT-05 / INT-04):
  --engine single  the Stage-3 raw tool-calling loop (default)
  --engine graph   the Stage-4 LangGraph supervisor
  --engine both    run each and print a side-by-side comparison

⚠️ This hits the real Anthropic API and spends tokens. It is capped at 30 cases
and requires --yes for more than 3 (so a full run is always deliberate); `both`
runs every case through BOTH engines, so it spends ~2x. Do a small run first
(default 2) to project the full cost.

Baseline (2026-07-13, sonnet-5, 30 cases, --engine both):
                       single        graph
  pass-rate (1st)       1.00          1.00     (same deterministic validator)
  degraded              0/30          0/30
  p50 latency          18.1s          6.8s
  tokens in         210,374        35,074
  tokens out         24,809         6,863
  est. cost          $1.003        $0.208
The perfect pass-rate reflects an easy gold set (structured queries, clear-cut
constraints) — the repair/fallback path never fired; it's proven by unit tests
instead. The headline surprise is cost/latency, NOT correctness: the graph is
~4.8x cheaper and ~2.7x faster because the raw single loop resends tool schemas
and accumulates adaptive-thinking every turn, while the graph confines the LLM
to picking from a code-pre-filtered shortlist + writing the summary. (Predicted
the reverse; measuring corrected it.)

Run:  python -m app.evals.run_agent                          # 2-case single dry run
      python -m app.evals.run_agent --engine both --limit 30 --yes
"""
from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass

from app.agent.loop import run_agent
from app.core.config import settings
from app.db import SessionLocal
from app.evals.common import load_cases
from app.llm.client import get_llm, is_enabled
from app.orchestrator.graph import build_graph, invoke_graph
from app.schemas.agent import AgentRequest

MAX_CASES = 30
# Claude Sonnet 5 standard pricing ($/1M tokens); intro rates are lower, so this
# is a conservative (over-)estimate.
COST_IN_PER_1M = 3.0
COST_OUT_PER_1M = 15.0


def _cost(tin: int, tout: int) -> float:
    return tin / 1_000_000 * COST_IN_PER_1M + tout / 1_000_000 * COST_OUT_PER_1M


@dataclass
class Row:
    name: str
    clean: bool  # constraint-clean on the first attempt (no repair, not degraded)
    degraded: bool
    repaired: bool
    tool_calls: int  # single engine only; -1 for graph (not applicable)
    wall: float
    tin: int
    tout: int
    top: str


def _req(case) -> AgentRequest:
    return AgentRequest(
        pantry=case.pantry,
        diet=case.diet,
        exclude_allergens=case.exclude_allergens,
        max_time_minutes=case.max_time_minutes,
        limit=2,
    )


def _run_single(session, case, client) -> Row:
    req = _req(case)
    t0 = time.perf_counter()
    r = run_agent(session, req, client=client)
    wall = time.perf_counter() - t0
    top = r.plan.recipes[0].title if r.plan and r.plan.recipes else "(none)"
    return Row(
        name=case.name, clean=not r.repaired and not r.degraded, degraded=r.degraded,
        repaired=r.repaired, tool_calls=r.tool_calls, wall=wall,
        tin=r.input_tokens, tout=r.output_tokens, top=top,
    )


def _run_graph(case) -> Row:
    req = _req(case)
    graph = build_graph()  # fresh per case; no checkpointer needed for the eval
    state_in = {"request": req.model_dump(), "repair_count": 0, "violations": [], "trace": []}
    t0 = time.perf_counter()
    final, tin, tout = invoke_graph(graph, state_in)
    wall = time.perf_counter() - t0
    degraded = final.get("degraded", False)
    repaired = final.get("repair_count", 0) > 0
    recipes = final.get("draft", {}).get("recipes", [])
    top = recipes[0]["title"] if recipes else "(none)"
    return Row(
        name=case.name, clean=not repaired and not degraded, degraded=degraded,
        repaired=repaired, tool_calls=-1, wall=wall, tin=tin, tout=tout, top=top,
    )


def _stats(engine: str, rows: list[Row]) -> dict:
    n = len(rows)
    needed_repair = [r for r in rows if r.repaired]
    repair_ok = sum(1 for r in needed_repair if not r.degraded)
    tin = sum(r.tin for r in rows)
    tout = sum(r.tout for r in rows)
    tool = [r.tool_calls for r in rows if r.tool_calls >= 0]
    return {
        "engine": engine, "n": n,
        "pass_rate": sum(r.clean for r in rows) / n,
        "clean": sum(r.clean for r in rows),
        "repair_ok": repair_ok, "needed_repair": len(needed_repair),
        "degraded": sum(r.degraded for r in rows),
        "mean_tools": statistics.mean(tool) if tool else None,
        "p50": statistics.median(sorted(r.wall for r in rows)),
        "tin": tin, "tout": tout, "cost": _cost(tin, tout),
    }


def _print_block(s: dict) -> None:
    n = s["n"]
    print("\n" + "=" * 60)
    print(f"  Agent eval — {n} cases, engine={s['engine']}, model={settings.LLM_MODEL_MAIN}")
    print("=" * 60)
    print(f"  constraint pass-rate (clean 1st try) : {s['pass_rate']:.2f}  ({s['clean']}/{n})")
    if s["needed_repair"]:
        print(f"  repair-success rate                  : {s['repair_ok'] / s['needed_repair']:.2f}  ({s['repair_ok']}/{s['needed_repair']})")
    else:
        print("  repair-success rate                  : n/a (no repairs needed)")
    print(f"  degraded rate                        : {s['degraded'] / n:.2f}  ({s['degraded']}/{n})")
    if s["mean_tools"] is not None:
        print(f"  mean tool calls                      : {s['mean_tools']:.1f}")
    print(f"  p50 latency                          : {s['p50']:.1f}s")
    print(f"  tokens                               : {s['tin']:,} in / {s['tout']:,} out")
    print(f"  estimated cost                       : ${s['cost']:.4f}  (@ ${COST_IN_PER_1M}/${COST_OUT_PER_1M} per 1M)")
    print(f"  projected 30-case cost               : ${s['cost'] / n * 30:.4f}")


def _print_compare(a: dict, b: dict) -> None:
    print("\n" + "=" * 64)
    print(f"  SINGLE vs GRAPH — {a['n']} cases, model={settings.LLM_MODEL_MAIN}")
    print("=" * 64)
    print(f"  {'metric':<26}{'single':>16}{'graph':>16}")
    print("  " + "-" * 60)

    def line(label, fa, fb):
        print(f"  {label:<26}{fa:>16}{fb:>16}")

    line("pass-rate (clean 1st)", f"{a['pass_rate']:.2f}", f"{b['pass_rate']:.2f}")
    line("degraded", f"{a['degraded']}/{a['n']}", f"{b['degraded']}/{b['n']}")
    line("p50 latency (s)", f"{a['p50']:.1f}", f"{b['p50']:.1f}")
    line("tokens in", f"{a['tin']:,}", f"{b['tin']:,}")
    line("tokens out", f"{a['tout']:,}", f"{b['tout']:,}")
    line("est. cost ($)", f"{a['cost']:.4f}", f"{b['cost']:.4f}")
    print("  " + "-" * 60)
    cheaper = "single" if a["cost"] <= b["cost"] else "graph"
    faster = "single" if a["p50"] <= b["p50"] else "graph"
    print(f"  cheaper: {cheaper}   faster (p50): {faster}")
    print("  (Same tools + same deterministic validator back both engines, so")
    print("   correctness matches. Cost/latency, however, are NOT a wash: the")
    print("   single loop resends tool schemas and accumulates thinking across")
    print("   turns, while the graph confines the LLM to picking from a")
    print("   pre-filtered shortlist + writing the summary — read the numbers")
    print("   above for this run rather than assuming which way it goes.)")


def _safe(fn, case) -> Row:
    """Run one case; on any failure record a degraded row so the run completes."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - eval must survive a single bad case
        print(f"  !! case {case.name!r} errored ({type(e).__name__}: {e}) — counted degraded")
        return Row(name=case.name, clean=False, degraded=True, repaired=False,
                   tool_calls=-1, wall=0.0, tin=0, tout=0, top="(error)")


def run(engine: str, limit: int, verbose: bool) -> None:
    cases = load_cases()[:limit]
    with SessionLocal() as session:
        if engine in ("single", "both"):
            client = get_llm().raw()
            single = [_safe(lambda c=c: _run_single(session, c, client), c) for c in cases]
        if engine in ("graph", "both"):
            graph_rows = [_safe(lambda c=c: _run_graph(c), c) for c in cases]

    if verbose:
        rows = single if engine != "graph" else graph_rows
        for r in rows:
            flag = "clean" if r.clean else ("degraded" if r.degraded else "repaired")
            print(f"  [{flag:8}] {r.name:40} top: {r.top}  ({r.wall:.0f}s)")

    if engine == "both":
        a, b = _stats("single", single), _stats("graph", graph_rows)
        _print_block(a)
        _print_block(b)
        _print_compare(a, b)
    elif engine == "single":
        _print_block(_stats("single", single))
    else:
        _print_block(_stats("graph", graph_rows))
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["single", "graph", "both"], default="single")
    ap.add_argument("--limit", type=int, default=2)
    ap.add_argument("--yes", action="store_true", help="required for more than 3 cases")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if not is_enabled():
        raise SystemExit("ANTHROPIC_API_KEY not set — the agent eval needs the real API.")

    limit = min(args.limit, MAX_CASES)
    if limit > 3 and not args.yes:
        mult = "2x (both engines)" if args.engine == "both" else ""
        raise SystemExit(
            f"About to run {limit} agent cases (engine={args.engine}) against the REAL "
            f"API (spends tokens{', ' + mult if mult else ''}).\n"
            f"Re-run with --yes to confirm, or use a smaller --limit for a dry run."
        )
    run(args.engine, limit, args.verbose)


if __name__ == "__main__":
    main()
