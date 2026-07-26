"""Thin Anthropic (Claude) adapter.

One seam for every LLM call in the app: model IDs and timeout come from config,
errors are normalized to `LLMError`, and structured output is schema-validated
via `client.messages.parse()`. Swapping providers later means rewriting only
this file. The client is created lazily so importing the app never requires a
key; `is_enabled()` gates the fail-open behavior in callers.
"""
from __future__ import annotations

import logging
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Normalized failure from any LLM call (API error, timeout, or bad output)."""


def is_enabled() -> bool:
    """True when an API key is configured; callers fail open when False."""
    return bool(settings.ANTHROPIC_API_KEY)


class LLMClient:
    def __init__(self) -> None:
        self._client = None  # lazy

    def _ensure(self):
        if self._client is None:
            if not is_enabled():
                raise LLMError("ANTHROPIC_API_KEY is not configured")
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        return self._client

    def raw(self):
        """The underlying anthropic.Anthropic client (for the agent loop, which
        needs direct messages.create/parse access). Raises LLMError if disabled."""
        return self._ensure()

    def generate(
        self, messages: list[dict], *, model: Optional[str] = None, max_tokens: int = 1024
    ) -> str:
        """Plain-text completion. Returns the concatenated text blocks."""
        import anthropic

        client = self._ensure()
        try:
            resp = client.messages.create(
                model=model or settings.LLM_MODEL_FAST,
                max_tokens=max_tokens,
                messages=messages,
            )
        except anthropic.APIError as e:  # covers status + connection errors
            raise LLMError(str(e)) from e
        return "".join(b.text for b in resp.content if b.type == "text")

    def generate_structured(
        self,
        messages: list[dict],
        schema: Type[T],
        *,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        timeout: Optional[float] = None,
    ) -> T:
        """Schema-validated completion via messages.parse(). Returns a `schema` instance.

        `timeout` overrides the client default for this call — writing several
        full recipes takes far longer than the short-prompt uses this adapter
        was first built for, and the default would abort them mid-generation.
        """
        import anthropic

        client = self._ensure()
        options = {"timeout": timeout} if timeout is not None else {}
        try:
            resp = client.messages.parse(
                model=model or settings.LLM_MODEL_FAST,
                max_tokens=max_tokens,
                messages=messages,
                output_format=schema,
                **options,
            )
        except anthropic.APIError as e:
            raise LLMError(str(e)) from e
        parsed = resp.parsed_output
        if parsed is None:
            raise LLMError(f"model did not return valid {schema.__name__} (stop={resp.stop_reason})")
        return parsed


_default: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    """Process-wide singleton adapter."""
    global _default
    if _default is None:
        _default = LLMClient()
    return _default
