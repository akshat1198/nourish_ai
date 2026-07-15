"""Stage 6.5 — Edamam web-search proxy. No DB; httpx mocked for the enabled path."""
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services import edamam

client = TestClient(app)


def test_disabled_is_fail_open():
    # No creds configured (test env) -> feature off, empty results, no error.
    r = client.get("/v1/search/web", params={"q": "pasta"})
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["results"] == []
    assert body["query"] == "pasta"


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_enabled_normalizes_hits(monkeypatch):
    monkeypatch.setattr(edamam.settings, "EDAMAM_APP_ID", "id")
    monkeypatch.setattr(edamam.settings, "EDAMAM_APP_KEY", "key")
    payload = {"hits": [
        {"recipe": {"label": "Chicken Curry", "url": "https://x.test/1",
                    "source": "BBC", "image": "https://x.test/1.jpg"}},
        {"recipe": {"label": "No URL", "source": "Y"}},  # dropped: no url
    ]}
    monkeypatch.setattr(edamam.httpx, "get", lambda *a, **k: _FakeResp(payload))

    r = client.get("/v1/search/web", params={"q": "curry"}).json()
    assert r["enabled"] is True
    assert len(r["results"]) == 1
    hit = r["results"][0]
    assert hit["title"] == "Chicken Curry"
    assert hit["url"] == "https://x.test/1"
    assert hit["source"] == "BBC"


def test_enabled_error_returns_empty(monkeypatch):
    monkeypatch.setattr(edamam.settings, "EDAMAM_APP_ID", "id")
    monkeypatch.setattr(edamam.settings, "EDAMAM_APP_KEY", "key")

    def _boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(edamam.httpx, "get", _boom)
    r = client.get("/v1/search/web", params={"q": "curry"}).json()
    assert r["enabled"] is True          # configured…
    assert r["results"] == []            # …but a live failure degrades to empty


def test_empty_query_no_call(monkeypatch):
    called = {"n": 0}

    def _count(*a, **k):
        called["n"] += 1
        return _FakeResp({"hits": []})

    monkeypatch.setattr(edamam.settings, "EDAMAM_APP_ID", "id")
    monkeypatch.setattr(edamam.settings, "EDAMAM_APP_KEY", "key")
    monkeypatch.setattr(edamam.httpx, "get", _count)
    client.get("/v1/search/web", params={"q": "   "})
    assert called["n"] == 0              # blank query never hits the API
