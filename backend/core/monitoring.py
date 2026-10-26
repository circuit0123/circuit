"""Sentry for the backend: errors with a stack trace, tagged with the environment and release, and nothing personal.

Sentry is a third party (PRODUCTION.md §5 lists it as a processor), so what leaves the server is cut down twice:
  1. the SDK is told not to collect it (no default PII, no local variables, no request bodies);
  2. `scrub_event` removes what could still slip in (headers, cookies, query strings, the user block, and emails, phone numbers or
     tokens that a developer put in an exception message).

With no SENTRY_DSN (dev, tests) `init_sentry` does nothing at all.
"""

import re
from typing import Any

import structlog

from core.logging import _BLOCKED

log = structlog.get_logger("monitoring")

REDACTED = "[redacted]"
_SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-forwarded-for", "x-real-ip", "x-api-key", "x-csrftoken"}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_JWT = re.compile(r"eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]*")
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[\w.~+/=-]{8,}")
_PHONE = re.compile(r"(?<![\w.])\+?\d[\d\s().-]{8,}\d(?![\w.])")


def scrub_text(text: str) -> str:
    for pattern in (_JWT, _BEARER, _EMAIL, _PHONE):
        text = pattern.sub(REDACTED, text)
    return text


def _blocked_key(key: str) -> bool:
    k = key.lower()
    return k in _BLOCKED or any(b in k for b in ("token", "password", "email", "secret", "authorization", "api_key", "cookie"))


def _scrub(value: Any) -> Any:
    """Walk an event: mask blocked keys, and mask personal patterns inside every string."""
    if isinstance(value, dict):
        return {k: (REDACTED if isinstance(k, str) and _blocked_key(k) else _scrub(v)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_scrub(v) for v in value]
    if isinstance(value, str):
        return scrub_text(value)
    return value


def scrub_event(event: Any, hint: Any = None) -> Any:
    request = event.get("request")
    if isinstance(request, dict):
        for key in ("data", "cookies", "query_string", "env"):
            request.pop(key, None)  # request bodies, cookies and query strings can all hold personal data or tokens
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {k: v for k, v in headers.items() if k.lower() not in _SENSITIVE_HEADERS}
        if isinstance(request.get("url"), str):
            request["url"] = request["url"].split("?", 1)[0]
    event.pop("user", None)  # no id, email, username or IP
    event.pop("server_name", None)
    return _scrub(event)


def scrub_breadcrumb(crumb: Any, hint: Any = None) -> Any:
    if crumb.get("category") in ("httplib", "http", "console"):
        return None  # outgoing calls carry URLs and bodies; the trace and the job logs are enough to debug
    return _scrub(crumb)


def init_sentry(dsn: str, *, environment: str, release: str, traces_sample_rate: float = 0.0) -> bool:
    """Start Sentry. True when it is on. Never raises: monitoring must not stop the app from starting."""
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release or None,
            data_collection={  # the SDK collects none of the personal categories; scrub_event is the second lock
                "user_info": False,
                "cookies": {"mode": "off"},
                "http_headers": {"request": {"mode": "off"}},
                "http_bodies": [],
                "url_query_params": {"mode": "off"},
                "database_query_data": False,
                "queues": False,
                "stack_frame_variables": False,
            },
            traces_sample_rate=traces_sample_rate,
            before_send=scrub_event,
            before_breadcrumb=scrub_breadcrumb,
            integrations=[DjangoIntegration()],
        )
    except Exception as exc:  # a bad DSN is logged and ignored
        log.error("sentry.init_failed", error=type(exc).__name__)
        return False
    return True


def capture_job_failure(job: str, exc: BaseException) -> None:
    """Report a failed scheduled job. A no-op when Sentry is not initialised."""
    try:
        import sentry_sdk

        if not sentry_sdk.is_initialized():
            return
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("job", job)
            scope.set_tag("kind", "scheduled_job")
            sentry_sdk.capture_exception(exc)
        sentry_sdk.flush(timeout=5)  # a job exits right after this; do not lose the event
    except Exception as err:
        log.warning("sentry.capture_failed", error=type(err).__name__)
