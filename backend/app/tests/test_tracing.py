"""Tracing tests — no API or DB.

persist_trace's reshaping is exercised with a fake session; the single-agent
loop's trail is captured by monkeypatching persist_trace; the traces endpoint
is exercised with fetch_trace stubbed.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agent import loop as loop_mod
from app.agent import tracing
from app.api import traces as traces_api
from app.api.deps import get_session
from app.main import app
from app.schemas.agent import AgentRequest, MealPlanItem, MealPlanResponse


class _FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


# --------------------------------------------------------------------------- #
# persist_trace
# --------------------------------------------------------------------------- #
def test_persist_trace_reshapes_events_into_rows():
    sess = _FakeSession()
    events = [
        {"node": "agent", "event_type": "llm", "tokens": 42, "latency_ms": 100, "iteration": 1},
        {"node": "tool:search_recipes", "event_type": "tool_use", "is_error": False},
    ]
    tracing.persist_trace(sess, "sess-1", "single", events)

    assert sess.committed
    assert len(sess.added) == 2
    first = sess.added[0]
    assert first.session_id == "sess-1" and first.engine == "single"
    assert first.node == "agent" and first.event_type == "llm"
    assert first.tokens == 42 and first.latency_ms == 100 and first.seq == 0
    # reserved keys are promoted to columns, not duplicated into payload
    assert first.payload == {"iteration": 1}
    assert "tokens" not in first.payload and "node" not in first.payload
    # defaults hold when a row omits token/latency
    assert sess.added[1].tokens == 0 and sess.added[1].payload == {"is_error": False}


@pytest.mark.parametrize(
    "session,session_id,events",
    [
        (None, "s", [{"node": "x"}]),        # no session
        (_FakeSession(), None, [{"node": "x"}]),  # no session_id
        (_FakeSession(), "s", []),            # nothing to write
    ],
)
def test_persist_trace_is_noop_without_prerequisites(session, session_id, events):
    tracing.persist_trace(session, session_id, "single", events)
    if isinstance(session, _FakeSession):
        assert session.added == [] and session.committed is False


# --------------------------------------------------------------------------- #
# single-agent loop builds a trail
# --------------------------------------------------------------------------- #
def test_single_loop_persists_a_trail(monkeypatch):
    captured = {}

    def fake_persist(session, session_id, engine, events):
        captured["engine"] = engine
        captured["session_id"] = session_id
        captured["events"] = events

    monkeypatch.setattr(loop_mod, "persist_trace", fake_persist)
    monkeypatch.setattr(loop_mod, "call_tool", lambda s, n, i: {"ok": True})
    monkeypatch.setattr(loop_mod, "validate_plan", lambda s, p, r: [])

    def _text(t):
        return SimpleNamespace(type="text", text=t)

    def _resp(stop, content):
        return SimpleNamespace(stop_reason=stop, content=content, usage=None)

    class _Msgs:
        def create(self, **k):
            return _resp("end_turn", [_text("done")])

        def parse(self, **k):
            return SimpleNamespace(
                parsed_output=MealPlanResponse(
                    recipes=[MealPlanItem(recipe_id=1, title="Pasta", why="fits")],
                    summary="ok",
                )
            )

    client = SimpleNamespace(messages=_Msgs())
    req = AgentRequest(pantry=["pasta"], session_id="sess-9")
    loop_mod.run_agent(session=_FakeSession(), request=req, client=client)

    assert captured["engine"] == "single"
    assert captured["session_id"] == "sess-9"
    nodes = [e["node"] for e in captured["events"]]
    assert "agent" in nodes and "structure" in nodes and nodes[-1] == "_run"
    assert captured["events"][-1]["event_type"] == "summary"


# --------------------------------------------------------------------------- #
# GET /v1/traces/{session_id}
# --------------------------------------------------------------------------- #
def _row(node, engine="graph", event_type="node", tokens=0, latency_ms=5, payload=None):
    return SimpleNamespace(
        node=node, engine=engine, event_type=event_type, tokens=tokens,
        latency_ms=latency_ms, payload=payload or {},
        created_at=datetime(2026, 7, 13, tzinfo=timezone.utc),
    )


def test_traces_endpoint_returns_ordered_events(monkeypatch):
    rows = [
        _row("pantry_analyst", latency_ms=3),
        _row("recipe_planner", event_type="llm", latency_ms=800),
        _row("_run", event_type="summary", tokens=1500, latency_ms=1200),
    ]
    monkeypatch.setattr(traces_api, "fetch_trace", lambda s, sid: rows)
    app.dependency_overrides[get_session] = lambda: object()
    try:
        resp = TestClient(app).get("/v1/traces/sess-1")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "sess-1" and body["engine"] == "graph"
    assert body["count"] == 3
    assert body["total_tokens"] == 1500
    assert body["total_latency_ms"] == 2003
    assert [e["node"] for e in body["events"]] == [
        "pantry_analyst", "recipe_planner", "_run",
    ]


def test_traces_endpoint_404_when_empty(monkeypatch):
    monkeypatch.setattr(traces_api, "fetch_trace", lambda s, sid: [])
    app.dependency_overrides[get_session] = lambda: object()
    try:
        resp = TestClient(app).get("/v1/traces/nope")
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert resp.status_code == 404
