"""Sentry gets errors, never people (PRODUCTION.md §5, CLAUDE.md privacy rules). No network: events go through a fake transport."""

import sentry_sdk
from sentry_sdk.transport import Transport

from core import jobs
from core.monitoring import REDACTED, capture_job_failure, init_sentry, scrub_breadcrumb, scrub_event, scrub_text

JWT = "eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJl"


class Capture(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.events: list[dict] = []

    def capture_envelope(self, envelope):
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


def start(release="abc123def456", env="staging"):
    """Initialise the SDK the way production does, but with the fake transport."""
    transport = Capture()
    ok = init_sentry("https://key@o0.ingest.sentry.io/1", environment=env, release=release)
    assert ok
    client = sentry_sdk.get_client()
    client.transport = transport
    return transport


def stop():
    sentry_sdk.get_client().close()
    sentry_sdk.init()  # back to a disabled client so other tests are untouched


def test_no_dsn_means_off():
    assert init_sentry("", environment="dev", release="") is False


def test_text_scrubbing_masks_emails_phones_and_tokens():
    text = f"failed for asha@example.com phone +91 98765 43210 token {JWT} header Bearer abcdefgh12345678 ok"
    out = scrub_text(text)
    for secret in ("asha@example.com", "98765", JWT, "abcdefgh12345678"):
        assert secret not in out
    assert out.count(REDACTED) == 4


def test_ordinary_text_and_dates_survive():
    assert (
        scrub_text("Job compute_matches took 4200 ms at 2026-10-26T13:41:06Z")
        == "Job compute_matches took 4200 ms at 2026-10-26T13:41:06Z"
    )


def test_event_loses_body_cookies_query_user_and_auth_headers():
    event = {
        "request": {
            "url": "https://api.example.com/api/me?email=asha@example.com",
            "query_string": "email=asha@example.com",
            "data": {"display_name": "Asha", "bio": "I build things"},
            "cookies": {"sessionid": "x"},
            "headers": {"Authorization": f"Bearer {JWT}", "Cookie": "a=b", "User-Agent": "pytest", "X-Forwarded-For": "1.2.3.4"},
        },
        "user": {"id": "42", "email": "asha@example.com", "ip_address": "1.2.3.4"},
        "extra": {"display_name": "Asha", "count": 3, "note": "mail asha@example.com"},
        "exception": {"values": [{"type": "ValueError", "value": f"bad token {JWT} for priya@example.com"}]},
    }
    out = scrub_event(event)
    flat = repr(out)
    for secret in ("Asha", "asha@example.com", "priya@example.com", JWT, "I build things", "1.2.3.4", "sessionid"):
        assert secret not in flat, secret
    assert "user" not in out
    assert out["request"]["url"] == "https://api.example.com/api/me"
    assert out["request"]["headers"] == {"User-Agent": "pytest"}
    assert out["extra"]["count"] == 3
    assert out["exception"]["values"][0]["type"] == "ValueError"


def test_http_and_console_breadcrumbs_are_dropped():
    assert scrub_breadcrumb({"category": "httplib", "data": {"url": "https://x"}}) is None
    kept = scrub_breadcrumb({"category": "query", "message": "user asha@example.com"})
    assert kept is not None and "asha@example.com" not in repr(kept)


def test_real_error_is_tagged_and_clean():
    transport = start(release="abc123def456", env="staging")
    try:
        sentry_sdk.set_user({"email": "asha@example.com", "id": "1"})
        try:
            raise ValueError("cannot reach asha@example.com")
        except ValueError as exc:
            sentry_sdk.capture_exception(exc)
        sentry_sdk.flush()
    finally:
        stop()
    assert len(transport.events) == 1
    event = transport.events[0]
    assert event["environment"] == "staging"
    assert event["release"] == "abc123def456"
    assert "asha@example.com" not in repr(event)
    assert "user" not in event or "email" not in event["user"]


def test_failed_job_is_reported_with_its_name(monkeypatch):
    transport = start()
    try:
        capture_job_failure("compute_matches", RuntimeError("boom"))
    finally:
        stop()
    assert transport.events[0]["tags"]["job"] == "compute_matches"
    assert jobs.capture_job_failure is capture_job_failure  # JobCommand calls the same function


def test_capture_without_sentry_is_a_noop():
    capture_job_failure("compute_matches", RuntimeError("boom"))
