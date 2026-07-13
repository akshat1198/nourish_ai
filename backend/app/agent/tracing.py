"""Shared agent tracing (Stage 4.4, AGENT-05).

One append-only trail — `agent_traces` — written by BOTH the Stage-3 single-agent
loop and the Stage-4 LangGraph orchestrator, so GET /v1/traces/{session_id} and
the comparative eval read one uniform shape regardless of engine.

`persist_trace` is best-effort and keyed by session_id: with no session_id
(eval runs, unit tests calling run_agent with session=None) nothing is written
and nothing breaks — traces are observability, never on the response's critical
path.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.models import AgentTrace

logger = logging.getLogger(__name__)

# Keys promoted to first-class columns; everything else on an event is payload.
_RESERVED = {"node", "event_type", "tokens", "latency_ms"}


def persist_trace(session, session_id, engine: str, events: list[dict]) -> None:
    """Append `events` as agent_traces rows. No-op without a session/session_id."""
    if session is None or not session_id or not events:
        return
    try:
        for seq, e in enumerate(events):
            payload = {k: v for k, v in e.items() if k not in _RESERVED}
            session.add(
                AgentTrace(
                    session_id=session_id,
                    engine=engine,
                    seq=seq,
                    node=e.get("node", ""),
                    event_type=e.get("event_type", "node"),
                    payload=payload,
                    tokens=int(e.get("tokens", 0) or 0),
                    latency_ms=int(e.get("latency_ms", 0) or 0),
                )
            )
        session.commit()
    except Exception as ex:  # tracing must never break the response
        session.rollback()
        logger.warning("failed to persist trace for %s: %s", session_id, ex)


def fetch_trace(session, session_id: str) -> list[AgentTrace]:
    """All rows for a session, in run order (created_at, then seq within a run)."""
    return list(
        session.execute(
            select(AgentTrace)
            .where(AgentTrace.session_id == session_id)
            .order_by(AgentTrace.created_at, AgentTrace.seq, AgentTrace.id)
        )
        .scalars()
        .all()
    )
