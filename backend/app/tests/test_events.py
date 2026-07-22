"""Online analytics event tests (Stage 13). DB-backed; append-only, cleaned up."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Event
from app.tests.conftest import requires_db

client = TestClient(app)


def _post(name, variant=None, recipe_id=None, session_id="test-session"):
    return client.post(
        "/v1/events",
        json={
            "name": name,
            "session_id": session_id,
            "recipe_id": recipe_id,
            "variant": variant,
            "props": {},
        },
        headers={"X-User-Key": "events-test-user"},
    )


@requires_db
def test_post_event_records_row(session):
    session.query(Event).filter_by(user_key="events-test-user").delete()
    session.commit()
    try:
        resp = _post("recipe_opened", variant="control")
        assert resp.status_code == 200
        row = session.execute(
            select(Event).where(Event.user_key == "events-test-user")
        ).scalar_one()
        assert row.name == "recipe_opened"
        assert row.variant == "control"
        assert row.session_id == "test-session"
    finally:
        session.query(Event).filter_by(user_key="events-test-user").delete()
        session.commit()


@requires_db
def test_experiment_summary_counts_per_variant(session):
    session.query(Event).filter_by(user_key="events-test-user").delete()
    session.commit()
    try:
        _post("results_shown", variant="control")
        _post("results_shown", variant="control")
        _post("cooked", variant="personalized")
        summary = client.get("/v1/experiments/ranking_ab/summary").json()
        assert summary["experiment"] == "ranking_ab"
        by_variant = {v["variant"]: v for v in summary["variants"]}
        assert by_variant["control"]["count"] >= 2
        assert by_variant["control"]["by_name"]["results_shown"] >= 2
        assert by_variant["personalized"]["by_name"]["cooked"] >= 1
    finally:
        session.query(Event).filter_by(user_key="events-test-user").delete()
        session.commit()


@requires_db
def test_experiment_summary_unknown_name_still_returns_shape(session):
    resp = client.get("/v1/experiments/nonexistent-experiment/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["experiment"] == "nonexistent-experiment"
    assert isinstance(body["total"], int)
    assert isinstance(body["variants"], list)
