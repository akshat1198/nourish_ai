"""LLM adapter + pantry-text parsing tests — fully mocked, no real API calls."""
from unittest.mock import MagicMock

import pytest

from app.llm.client import LLMClient, LLMError
from app.schemas.llm import ParsedPantry


def _client_with(fake_anthropic_client):
    c = LLMClient()
    c._client = fake_anthropic_client  # bypass lazy _ensure()
    return c


def test_generate_structured_returns_parsed(monkeypatch):
    fake = MagicMock()
    fake.messages.parse.return_value = MagicMock(
        parsed_output=ParsedPantry(items=["spinach", "eggs"], notes=""),
        stop_reason="end_turn",
    )
    client = _client_with(fake)
    result = client.generate_structured(
        messages=[{"role": "user", "content": "x"}], schema=ParsedPantry
    )
    assert result.items == ["spinach", "eggs"]


def test_generate_structured_none_output_raises():
    fake = MagicMock()
    fake.messages.parse.return_value = MagicMock(parsed_output=None, stop_reason="refusal")
    client = _client_with(fake)
    with pytest.raises(LLMError):
        client.generate_structured(
            messages=[{"role": "user", "content": "x"}], schema=ParsedPantry
        )


def test_api_error_is_normalized(monkeypatch):
    import anthropic

    fake = MagicMock()

    def boom(**kwargs):
        raise anthropic.APIError("kaboom", request=MagicMock(), body=None)

    fake.messages.parse.side_effect = boom
    client = _client_with(fake)
    with pytest.raises(LLMError):
        client.generate_structured(
            messages=[{"role": "user", "content": "x"}], schema=ParsedPantry
        )


def test_parse_pantry_text_fails_open_when_disabled(monkeypatch):
    # No API key -> is_enabled() False -> empty list, no exception.
    from app.services import pantry_text

    monkeypatch.setattr(pantry_text, "is_enabled", lambda: False)
    assert pantry_text.parse_pantry_text("leftover chicken and rice") == []


def test_parse_pantry_text_uses_llm(monkeypatch):
    from app.services import pantry_text

    monkeypatch.setattr(pantry_text, "is_enabled", lambda: True)
    fake_llm = MagicMock()
    fake_llm.generate_structured.return_value = ParsedPantry(
        items=["chicken breast", "rice"], notes=""
    )
    monkeypatch.setattr(pantry_text, "get_llm", lambda: fake_llm)
    assert pantry_text.parse_pantry_text("some leftover chicken and rice") == [
        "chicken breast",
        "rice",
    ]


def test_parse_pantry_text_fails_open_on_llm_error(monkeypatch):
    from app.services import pantry_text

    monkeypatch.setattr(pantry_text, "is_enabled", lambda: True)
    fake_llm = MagicMock()
    fake_llm.generate_structured.side_effect = LLMError("down")
    monkeypatch.setattr(pantry_text, "get_llm", lambda: fake_llm)
    assert pantry_text.parse_pantry_text("chicken") == []
