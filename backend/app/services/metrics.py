"""Observability aggregation (Stage 14). Read-only rollups over telemetry
that's already being logged (`generation_events`, `agent_traces`, `events`,
Redis cache counters) — no new data model, just a view over what exists.
"""
from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentTrace, Event, GenerationEvent
from app.services.cache import cache_metrics

RECENT_RUNS_LIMIT = 500


def _percentiles(values: list[int]) -> dict:
    if not values:
        return {"p50": None, "p95": None}
    p50, p95 = np.percentile(values, [50, 95])
    return {"p50": round(float(p50), 1), "p95": round(float(p95), 1)}


def admin_metrics(session: Session) -> dict:
    rows = (
        session.execute(
            select(GenerationEvent)
            .order_by(GenerationEvent.created_at.desc())
            .limit(RECENT_RUNS_LIMIT)
        )
        .scalars()
        .all()
    )

    runs = len(rows)
    latency = _percentiles([r.latency_ms for r in rows if r.latency_ms is not None])
    degraded_rate = round(sum(r.degraded for r in rows) / runs, 4) if runs else 0.0
    repaired_rate = round(sum(r.repaired for r in rows) / runs, 4) if runs else 0.0
    violation_runs = sum(1 for r in rows if r.violations)

    by_model: dict[str, int] = {}
    by_prompt_version: dict[str, int] = {}
    for r in rows:
        by_model[r.model] = by_model.get(r.model, 0) + 1
        by_prompt_version[r.prompt_version] = by_prompt_version.get(r.prompt_version, 0) + 1

    # Run-total tokens live on AgentTrace's "summary" rows (per-node rows would
    # double count); fall back to summing everything if no summary rows exist
    # (e.g. an engine/version that never wrote one).
    summary_tokens = session.execute(
        select(AgentTrace.tokens).where(AgentTrace.event_type == "summary")
    ).scalars().all()
    if summary_tokens:
        tokens_total = int(sum(summary_tokens))
    else:
        all_tokens = session.execute(select(AgentTrace.tokens)).scalars().all()
        tokens_total = int(sum(all_tokens))

    event_rows = session.execute(select(Event.name)).scalars().all()
    events_by_name: dict[str, int] = {}
    for name in event_rows:
        events_by_name[name] = events_by_name.get(name, 0) + 1

    return {
        "runs": runs,
        "latency_ms": latency,
        "degraded_rate": degraded_rate,
        "repaired_rate": repaired_rate,
        "violation_runs": violation_runs,
        "by_model": by_model,
        "by_prompt_version": by_prompt_version,
        "tokens_total": tokens_total,
        "cache": cache_metrics(),
        "events": {"total": len(event_rows), "by_name": events_by_name},
    }
