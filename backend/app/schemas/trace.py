"""Trace read schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    node: str
    engine: str
    event_type: str
    payload: dict = Field(default_factory=dict)
    tokens: int = 0
    latency_ms: int = 0
    created_at: datetime


class TraceResponse(BaseModel):
    session_id: str
    engine: str  # engine of the most recent run in this session
    count: int
    total_tokens: int
    total_latency_ms: int
    events: list[TraceEvent]
