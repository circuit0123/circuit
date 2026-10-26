#!/usr/bin/env python3
"""Smoke test for a deployed (or local) Circuit API: does it answer, and is it locked down the way it should be?

    make smoke URL=https://circuit-production-api-123.asia-south1.run.app ORIGIN=https://app.example.com
    python scripts/smoke.py URL [--origin APP_ORIGIN ...] [--expect-env production]

Checks, each printed as PASS / WARN / FAIL (the exit code is 1 if anything FAILs; WARN is information):
  /health            the process is up
  /ready             Postgres answers (Redis down is a WARN: the app reads Postgres instead)
  /api/config        public, and says which environment it is
  /api/openapi.json  served everywhere except production, where it must be hidden
  /api/me            a protected endpoint refuses a missing token, and a made-up one, in the standard error format
  CORS               each ORIGIN you pass is allowed (exactly), and an unknown origin is not
  headers            HSTS on https, nosniff and a content-security-policy everywhere

It only reads (GET, OPTIONS), never signs in, and sends no personal data. Standard library only, so it runs anywhere.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable

EVIL_ORIGIN = "https://evil.example"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is a result to report (http -> https, www -> bare), not something to follow silently."""

    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


def fetch(url: str, method: str = "GET", headers: dict | None = None, timeout: float = 30) -> tuple[int, dict, str]:
    """(status, lower-cased response headers, body). A refusal (4xx/5xx) is a normal answer, not an exception."""
    request = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with OPENER.open(request, timeout=timeout) as response:
            return (
                response.status,
                {k.lower(): v for k, v in response.headers.items()},
                response.read().decode("utf-8", "replace"),
            )
    except urllib.error.HTTPError as err:
        return err.code, {k.lower(): v for k, v in err.headers.items()}, err.read().decode("utf-8", "replace")


def as_json(body: str):
    try:
        return json.loads(body)
    except ValueError:
        return None


class Report:
    def __init__(self, out: Callable[[str], None] = print):
        self.out, self.failed, self.warned = out, 0, 0

    def line(self, level: str, name: str, detail: str) -> None:
        self.out(f"{level:<5} {name:<22} {detail}")
        if level == "FAIL":
            self.failed += 1
        elif level == "WARN":
            self.warned += 1

    def check(self, ok: bool, name: str, good: str, bad: str) -> bool:
        self.line("PASS" if ok else "FAIL", name, good if ok else bad)
        return ok


def run(base: str, origins: list[str], expect_env: str | None, timeout: float, out: Callable[[str], None] = print) -> int:
    base = base.rstrip("/")
    report = Report(out)
    out(f"Smoke test of {base}\n")

    def get(path: str, **kw):
        started = time.monotonic()
        status, headers, body = fetch(base + path, timeout=timeout, **kw)
        return status, headers, body, f"{round((time.monotonic() - started) * 1000)} ms"

    # A scaled-to-zero Cloud Run service needs a few seconds to wake up: the first answer may be slow or fail once.
    for attempt in range(3):
        try:
            status, _, body, took = get("/health")
            break
        except OSError as exc:
            if attempt == 2:
                report.line("FAIL", "/health", f"no answer: {exc}")
                out("\nFAILED: the service is not reachable, so the other checks were not run.")
                return 1
            time.sleep(5)
    report.check(
        status == 200 and (as_json(body) or {}).get("status") == "ok", "/health", f"200 ok ({took})", f"got {status}: {body[:80]}"
    )

    status, _, body, took = get("/ready")
    ready = as_json(body) or {}
    if status == 200 and ready.get("status") == "ok":
        report.line("PASS", "/ready", f"200 ok, Postgres and Redis answer ({took})")
    elif status == 200 and ready.get("status") == "degraded":
        report.line(
            "WARN",
            "/ready",
            f"200 degraded: {ready.get('redis')=} - the app works from Postgres, but fix Redis (REDIS_URL, Upstash)",
        )
    else:
        report.line("FAIL", "/ready", f"got {status} {body[:80]} - Postgres is not answering (DATABASE_URL, pooler, network)")

    status, config_headers, body, took = get("/api/config")
    config = as_json(body) or {}
    shape = (
        isinstance(config.get("env"), str)
        and isinstance(config.get("beta_mode"), bool)
        and isinstance(config.get("features"), dict)
    )
    report.check(
        status == 200 and shape,
        "/api/config",
        f"200, env={config.get('env')} beta_mode={config.get('beta_mode')} ({took})",
        f"got {status}: {body[:80]}",
    )
    env = config.get("env")
    if expect_env:
        report.check(
            env == expect_env, "environment", f"it is {expect_env}", f"expected {expect_env} but the service says {env!r}"
        )

    status, _, body, _ = get("/api/openapi.json")
    if env == "production":
        report.check(
            status == 404,
            "/api/openapi.json",
            "hidden in production, as designed",
            f"got {status}: the API description must not be public in production",
        )
    else:
        spec = as_json(body) or {}
        report.check(
            status == 200 and "/api/config" in spec.get("paths", {}),
            "/api/openapi.json",
            f"served, {len(spec.get('paths', {}))} paths",
            f"got {status}",
        )

    for label, headers in (("no token", {}), ("made-up token", {"Authorization": "Bearer not-a-real-token"})):
        status, _, body, _ = get("/api/me", headers=headers)
        error = (as_json(body) or {}).get("error") or {}
        ok = status == 401 and {"code", "message"} <= set(error)
        report.check(
            ok,
            f"/api/me ({label})",
            "401 in the standard error format",
            f"got {status}: {body[:80]} - a protected endpoint must refuse this",
        )

    preflight = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}
    for origin in origins:
        status, headers, _, _ = get("/api/me", method="OPTIONS", headers={"Origin": origin, **preflight})
        allowed = headers.get("access-control-allow-origin")
        report.check(
            status in (200, 204) and allowed == origin,
            f"CORS {origin}",
            "allowed",
            f"status {status}, Access-Control-Allow-Origin={allowed!r} - set CORS_ALLOWED_ORIGINS to exactly this",
        )
        report.check(
            "access-control-allow-credentials" not in headers,
            "CORS credentials",
            "cookies are not sent cross-origin",
            "credentials are allowed cross-origin",
        )
    status, headers, _, _ = get("/api/me", method="OPTIONS", headers={"Origin": EVIL_ORIGIN, **preflight})
    allowed = headers.get("access-control-allow-origin")
    report.check(
        allowed is None, f"CORS {EVIL_ORIGIN}", "refused (no Access-Control-Allow-Origin)", f"it was allowed: {allowed!r}"
    )
    if not origins:
        report.line(
            "WARN",
            "CORS",
            "no --origin given, so only the refusal was checked. Pass your app address: ORIGIN=https://app.example.com",
        )

    if base.startswith("https://"):
        report.check(
            "max-age" in config_headers.get("strict-transport-security", ""),
            "HSTS",
            "Strict-Transport-Security is set",
            "missing - browsers could be downgraded to http",
        )
    report.check(
        config_headers.get("x-content-type-options") == "nosniff", "nosniff", "X-Content-Type-Options: nosniff", "missing"
    )
    report.check(
        "default-src" in config_headers.get("content-security-policy", ""), "CSP", "Content-Security-Policy is set", "missing"
    )

    out(f"\n{'FAILED' if report.failed else 'OK'}: {report.failed} failed, {report.warned} warning(s)")
    return 1 if report.failed else 0


def main(argv: list[str] | None = None, out: Callable[[str], None] = print) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("url", help="the API address, e.g. https://circuit-production-api-123.asia-south1.run.app")
    ap.add_argument(
        "--origin", action="append", default=[], help="an app address that must be allowed by CORS (repeat for several)"
    )
    ap.add_argument("--expect-env", help="fail unless /api/config reports this environment")
    ap.add_argument("--timeout", type=float, default=30)
    args = ap.parse_args(argv)
    origins = [o.strip().rstrip("/") for item in args.origin for o in item.split(",") if o.strip()]
    return run(args.url, origins, args.expect_env, args.timeout, out)


if __name__ == "__main__":
    sys.exit(main())
