"""Authorization and quota on the two endpoints that spend money.

Both /v1/agent/recommend and /v1/orchestrate/plan took `user_key` straight from
the request body with no auth dependency, which meant an anonymous caller could
read and write any user's profile by naming them -- on an endpoint billing about
$0.21 a call. These tests pin the fixes so neither can regress quietly.
"""
import pytest
from fastapi import HTTPException

from app.api.agent import authorize_llm_call
from app.api.auth import scope_session_id
from app.core.config import settings
from app.schemas.agent import AgentRequest
from app.services import rate_limit


@pytest.fixture(autouse=True)
def _no_quota(monkeypatch):
    """Default these tests to an unlimited quota; the quota tests opt back in."""
    monkeypatch.setattr(settings, "AGENT_DAILY_LIMIT", 0)


def test_body_user_key_is_overwritten_by_the_token():
    """The decisive one: naming someone else must not reach their data."""
    req = AgentRequest(pantry=["egg"], user_key="google:victim")
    authorize_llm_call(req, "google:attacker", "agent")
    assert req.user_key == "google:attacker"


def test_session_id_is_scoped_to_its_owner():
    """Two users passing the same session id must not share a thread or trail."""
    a = AgentRequest(pantry=["egg"], session_id="s1")
    b = AgentRequest(pantry=["egg"], session_id="s1")
    authorize_llm_call(a, "google:alice", "orchestrate")
    authorize_llm_call(b, "google:bob", "orchestrate")
    assert a.session_id != b.session_id
    assert a.session_id == "google:alice:s1"


def test_absent_session_id_stays_absent():
    """No session means no checkpoint; it must not become the string 'None'."""
    req = AgentRequest(pantry=["egg"])
    authorize_llm_call(req, "google:alice", "agent")
    assert req.session_id is None
    assert scope_session_id("google:alice", None) is None


def test_quota_refuses_past_the_limit(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_DAILY_LIMIT", 2)
    calls = {"n": 0}

    def fake_consume(bucket, user_key, limit):
        calls["n"] += 1
        if calls["n"] > limit:
            raise rate_limit.RateLimitExceeded(bucket, limit, calls["n"])
        return limit - calls["n"]

    monkeypatch.setattr("app.api.agent.consume", fake_consume)
    for _ in range(2):
        authorize_llm_call(AgentRequest(pantry=["egg"]), "google:alice", "agent")
    with pytest.raises(HTTPException) as e:
        authorize_llm_call(AgentRequest(pantry=["egg"]), "google:alice", "agent")
    assert e.value.status_code == 429


def test_unreachable_redis_refuses_the_call(monkeypatch):
    """Fails CLOSED. A quota that cannot be counted must not be waived --
    Redis was down for weeks on this deployment, which would otherwise have
    been weeks of unmetered spend."""
    monkeypatch.setattr(settings, "AGENT_DAILY_LIMIT", 5)

    def boom(bucket, user_key, limit):
        raise rate_limit.RateLimitUnavailable("connection refused")

    monkeypatch.setattr("app.api.agent.consume", boom)
    with pytest.raises(HTTPException) as e:
        authorize_llm_call(AgentRequest(pantry=["egg"]), "google:alice", "agent")
    assert e.value.status_code == 503


def test_quota_disabled_by_zero(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_DAILY_LIMIT", 0)
    assert rate_limit.consume("agent", "google:alice", 0) == -1
