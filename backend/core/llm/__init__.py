"""LLM behind one interface (LLM_PROVIDER = gemini | groq | anthropic | none | fake).

Contract: `extract_json` returns a validated pydantic object or None. It never raises.
Callers treat None as "fall back to manual pickers". Every call has a timeout and
retries with backoff.

Two ways to run without paying for (or while out of) LLM calls, both ending in the manual pickers:
  - LLM_PROVIDER=none: no provider at all. `extract_json` returns None at once and never touches the network or the database.
  - LLM_DAILY_CALL_LIMIT=N: at most N provider calls per India day, counted in Postgres (core/usage.py), across every instance.
    Past it `extract_json` returns None and logs `llm.cap_reached`; tomorrow it works again. 0 = no cap.
"""

import json
import time
from typing import Protocol, TypeVar

import structlog
from django.conf import settings
from pydantic import BaseModel, ValidationError

log = structlog.get_logger("llm")
T = TypeVar("T", bound=BaseModel)

TIMEOUT_SECONDS = 15
MAX_ATTEMPTS = 3


class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class FakeLLM:
    """Returns canned text. Tests set `.response` (or `.error`)."""

    def __init__(self, response: str = "{}", error: Exception | None = None):
        self.response, self.error, self.calls = response, error, 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if self.error:
            raise self.error
        return self.response


class NoLLM:
    """LLM_PROVIDER=none. `extract_json` never calls it; if something does, that is a bug worth seeing."""

    def complete(self, system: str, user: str) -> str:
        raise RuntimeError("LLM_PROVIDER=none: no language model is configured")


class GroqLLM:
    def complete(self, system: str, user: str) -> str:
        from groq import Groq

        client = Groq(api_key=settings.GROQ_API_KEY, timeout=TIMEOUT_SECONDS, max_retries=0)
        out = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return out.choices[0].message.content or ""


class GeminiLLM:
    def complete(self, system: str, user: str) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000))
        out = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json", temperature=0),
        )
        return out.text or ""


class AnthropicLLM:
    def complete(self, system: str, user: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=TIMEOUT_SECONDS, max_retries=0)
        out = client.messages.create(
            model="claude-haiku-5-5", max_tokens=1024, system=system, messages=[{"role": "user", "content": user}]
        )
        return "".join(b.text for b in out.content if b.type == "text")


_provider: LLMProvider | None = None


def get_llm() -> LLMProvider:
    global _provider
    if _provider is None:
        factories: dict[str, type[LLMProvider]] = {
            "groq": GroqLLM,
            "gemini": GeminiLLM,
            "anthropic": AnthropicLLM,
            "none": NoLLM,
            "fake": FakeLLM,
        }
        _provider = factories[settings.LLM_PROVIDER]()
    return _provider


def set_llm(provider: LLMProvider | None) -> None:
    global _provider
    _provider = provider


def _has_key() -> bool:
    return bool(
        {"groq": settings.GROQ_API_KEY, "gemini": settings.GEMINI_API_KEY, "anthropic": settings.ANTHROPIC_API_KEY}.get(
            settings.LLM_PROVIDER, "x"
        )
    )


def _within_daily_cap() -> bool:
    """Count one provider call against today's cap. True = go ahead. A database problem never blocks onboarding."""
    limit = settings.LLM_DAILY_CALL_LIMIT
    if not limit:
        return True
    from core import usage

    try:
        used = usage.bump("llm_calls")
    except Exception as exc:
        log.warning("llm_cap_unavailable", error=type(exc).__name__)
        return True
    if used > limit:
        log.warning("llm.cap_reached", limit=limit)
        return False
    return True


def extract_json(system: str, user: str, schema: type[T]) -> T | None:
    if settings.LLM_PROVIDER == "none":
        return None  # manual pickers; no key, no network, no database
    provider = get_llm()
    if isinstance(provider, (GroqLLM, GeminiLLM, AnthropicLLM)) and not _has_key():
        log.warning("llm_no_api_key", provider=settings.LLM_PROVIDER)
        return None
    for attempt in range(MAX_ATTEMPTS):
        if not _within_daily_cap():
            return None
        try:
            raw = provider.complete(system, user)
            return schema.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError):
            log.warning("llm_invalid_output", attempt=attempt)  # retrying a malformed answer rarely helps
            return None
        except Exception as exc:  # network, timeout, rate limit
            log.warning("llm_call_failed", attempt=attempt, error=type(exc).__name__)
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(0.5 * 2**attempt)
    return None
