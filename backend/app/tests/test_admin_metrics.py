"""Admin observability endpoint tests. DB-backed; append-only
tables, cleaned up via a distinct marker in each row so nothing else's
historical data pollutes the assertions."""
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models import GenerationEvent
from app.tests.conftest import requires_db

client = TestClient(app)

MARKER_USER = "admin-metrics-test-marker"


@requires_db
def test_metrics_requires_admin_token(session, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "secret-token")
    # no header at all
    assert client.get("/v1/admin/metrics").status_code == 403
    # wrong token
    assert (
        client.get(
            "/v1/admin/metrics", headers={"X-Admin-Token": "wrong"}
        ).status_code
        == 403
    )
    # correct token
    assert (
        client.get(
            "/v1/admin/metrics", headers={"X-Admin-Token": "secret-token"}
        ).status_code
        == 200
    )


@requires_db
def test_metrics_locked_even_with_a_header_when_token_unset(session, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "")
    resp = client.get("/v1/admin/metrics", headers={"X-Admin-Token": ""})
    assert resp.status_code == 403


@requires_db
def test_metrics_aggregation_correct(session, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "secret-token")
    session.query(GenerationEvent).filter_by(user_key=MARKER_USER).delete()
    session.commit()
    try:
        rows = [
            GenerationEvent(
                user_key=MARKER_USER, prompt_version="v1", model="claude-sonnet-5",
                violations=[], repaired=False, degraded=False, latency_ms=100,
            ),
            GenerationEvent(
                user_key=MARKER_USER, prompt_version="v1", model="claude-sonnet-5",
                violations=["disliked"], repaired=True, degraded=False, latency_ms=200,
            ),
            GenerationEvent(
                user_key=MARKER_USER, prompt_version="v2", model="claude-haiku-4-5",
                violations=[], repaired=False, degraded=True, latency_ms=300,
            ),
        ]
        session.add_all(rows)
        session.commit()

        resp = client.get(
            "/v1/admin/metrics", headers={"X-Admin-Token": "secret-token"}
        )
        assert resp.status_code == 200
        body = resp.json()

        # These 3 marker rows are the most recent (created just now), so with
        # the default recency-ordered limit they're included; assert on
        # relative/marker-scoped facts rather than exact totals (historical
        # rows from other runs may already exist in this DB).
        assert body["runs"] >= 3
        assert body["latency_ms"]["p50"] is not None
        assert 0.0 <= body["degraded_rate"] <= 1.0
        assert 0.0 <= body["repaired_rate"] <= 1.0
        assert body["violation_runs"] >= 1
        assert body["by_model"].get("claude-sonnet-5", 0) >= 2
        assert body["by_model"].get("claude-haiku-4-5", 0) >= 1
        assert "cache" in body and "hit_rate" in body["cache"]
        assert "events" in body and "total" in body["events"]
        assert isinstance(body["tokens_total"], int)
    finally:
        session.query(GenerationEvent).filter_by(user_key=MARKER_USER).delete()
        session.commit()
