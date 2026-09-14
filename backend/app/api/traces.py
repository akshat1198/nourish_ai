"""Trace endpoint: GET /v1/traces/{session_id}.

Reads the append-only agent_traces trail for a session — every node/step, its
tokens and latency — for both engines. Pure observability; append-only rows,
no UI.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.tracing import fetch_trace
from app.api.auth import get_current_user_key, scope_session_id
from app.api.deps import get_session
from app.schemas.trace import TraceEvent, TraceResponse

router = APIRouter(prefix="/v1", tags=["traces"])


@router.get("/traces/{session_id}", response_model=TraceResponse)
def get_traces(
    session_id: str,
    session: Session = Depends(get_session),
    user_key: str = Depends(get_current_user_key),
):
    # Traces carry the caller's pantry and their plan. Read through the same
    # scoping the writer used, so a session id names only its owner's trail --
    # a 404 for someone else's id, not a 403, since existence is not theirs
    # to learn either.
    rows = fetch_trace(session, scope_session_id(user_key, session_id))
    if not rows:
        raise HTTPException(404, f"no traces for session {session_id!r}")
    events = [
        TraceEvent(
            node=r.node,
            engine=r.engine,
            event_type=r.event_type,
            payload=r.payload,
            tokens=r.tokens,
            latency_ms=r.latency_ms,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return TraceResponse(
        session_id=session_id,
        engine=rows[-1].engine,
        count=len(events),
        total_tokens=sum(r.tokens for r in rows),
        total_latency_ms=sum(r.latency_ms for r in rows),
        events=events,
    )
