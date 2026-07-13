"""Smoke tests for the API skeleton.

test_health_reports_services expects the docker compose stack (db + redis)
to be running — start it with `make up` first.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_api_info():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["docs"] == "/docs"
    assert body["health"] == "/health"


def test_health_reports_services():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"status", "db", "redis", "version"}
    assert body["status"] == "ok"
    assert body["db"] is True
    assert body["redis"] is True
