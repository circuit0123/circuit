"""LLM behind one interface (LLM_PROVIDER = gemini | groq | anthropic | fake).

Contract: `extract_json` returns a validated pydantic object or None. It never raises.
Callers treat None as "fall back to manual pickers". Every call has a timeout and
retries with backoff.
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


def extract_json(system: str, user: str, schema: type[T]) -> T | None:
    provider = get_llm()
    if isinstance(provider, (GroqLLM, GeminiLLM, AnthropicLLM)) and not _has_key():
        log.warning("llm_no_api_key", provider=settings.LLM_PROVIDER)
        return None
    for attempt in range(MAX_ATTEMPTS):
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
