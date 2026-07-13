"""Auth dependency tests (Stage 5) — no DB, no Google.

Exercises both AUTH_MODE branches by calling the dependency directly with a
minimal request stub and an inline-minted PyJWT token.
"""
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException

from app.api.auth import get_current_user_key
from app.core.config import settings


def _req(headers: dict) -> SimpleNamespace:
    return SimpleNamespace(headers=headers)  # .headers.get(...) works on a dict


def _mint(secret: str, **claims) -> str:
    payload = {"sub": "123", "aud": settings.AUTH_JWT_AUD, "iss": settings.AUTH_JWT_ISS}
    payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


def test_disabled_mode_uses_x_user_key(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "disabled")
    assert get_current_user_key(_req({"X-User-Key": "u1"})) == "u1"


def test_disabled_mode_defaults_to_dev_user(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "disabled")
    assert get_current_user_key(_req({})) == "dev-user"


def test_jwt_mode_accepts_valid_token(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "jwt")
    monkeypatch.setattr(settings, "AUTH_SHARED_SECRET", "s3cret")
    token = _mint("s3cret")
    assert get_current_user_key(_req({"Authorization": f"Bearer {token}"})) == "google:123"


def test_jwt_mode_ignores_x_user_key(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "jwt")
    monkeypatch.setattr(settings, "AUTH_SHARED_SECRET", "s3cret")
    with pytest.raises(HTTPException) as e:  # X-User-Key is not a token -> 401
        get_current_user_key(_req({"X-User-Key": "spoof"}))
    assert e.value.status_code == 401


def test_jwt_mode_rejects_wrong_secret(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "jwt")
    monkeypatch.setattr(settings, "AUTH_SHARED_SECRET", "s3cret")
    token = _mint("WRONG-SECRET")
    with pytest.raises(HTTPException):
        get_current_user_key(_req({"Authorization": f"Bearer {token}"}))


def test_jwt_mode_rejects_wrong_audience(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "jwt")
    monkeypatch.setattr(settings, "AUTH_SHARED_SECRET", "s3cret")
    token = _mint("s3cret", aud="some-other-api")
    with pytest.raises(HTTPException):
        get_current_user_key(_req({"Authorization": f"Bearer {token}"}))
