"""scripts/smoke.py against the real local server (pytest-django's live_server) and against a stub that is wrong on purpose."""

import importlib.util
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from django.conf import settings

SCRIPT = settings.BASE_DIR.parent / "scripts" / "smoke.py"
spec = importlib.util.spec_from_file_location("smoke", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
sys.modules["smoke"] = smoke
spec.loader.exec_module(smoke)

APP_ORIGIN = "http://localhost:3000"


def run(url, origins=(), expect_env=None):
    lines: list[str] = []
    code = smoke.run(url, list(origins), expect_env, 5, lines.append)
    return code, "\n".join(lines)


# ---- the real local server ---------------------------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_the_real_api_passes_every_check(live_server):
    code, text = run(live_server.url, [settings.CORS_ALLOWED_ORIGINS[0]], expect_env="dev")
    assert code == 0, text
    for name in (
        "/health",
        "/ready",
        "/api/config",
        "/api/openapi.json",
        "/api/me (no token)",
        "/api/me (made-up token)",
        "nosniff",
        "CSP",
    ):
        assert any(line.startswith("PASS") and name in line for line in text.splitlines()), f"{name} did not pass:\n{text}"
    assert "FAIL" not in text


@pytest.mark.django_db(transaction=True)
def test_an_origin_the_server_does_not_allow_fails_the_smoke_test(live_server):
    code, text = run(live_server.url, ["https://not-configured.example"])
    assert code == 1 and "FAIL  CORS https://not-configured.example" in text


@pytest.mark.django_db(transaction=True)
def test_the_wrong_environment_fails(live_server):
    code, text = run(live_server.url, [APP_ORIGIN], expect_env="production")
    assert code == 1 and "expected production" in text


@pytest.mark.django_db(transaction=True)
def test_redis_down_is_a_warning_and_still_passes(live_server, monkeypatch):
    from core import cache

    monkeypatch.setattr(cache.Cache, "ping", lambda self: False)
    code, text = run(live_server.url, [settings.CORS_ALLOWED_ORIGINS[0]])
    assert code == 0 and "WARN  /ready" in text


@pytest.mark.django_db(transaction=True)
def test_the_command_line_exits_zero_on_success_and_non_zero_on_failure(live_server):
    ok = subprocess.run(
        [sys.executable, str(SCRIPT), live_server.url, "--origin", settings.CORS_ALLOWED_ORIGINS[0]],
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0 and "OK: 0 failed" in ok.stdout
    bad = subprocess.run(
        [sys.executable, str(SCRIPT), live_server.url, "--origin", "https://nope.example"], capture_output=True, text=True
    )
    assert bad.returncode == 1 and "FAILED" in bad.stdout


def test_an_unreachable_service_fails_fast_with_a_clear_message(monkeypatch):
    monkeypatch.setattr(smoke.time, "sleep", lambda s: None)
    code, text = run("http://127.0.0.1:9")  # nothing listens on the discard port
    assert code == 1 and "FAIL  /health" in text and "not reachable" in text


# ---- a stub that gets things wrong on purpose --------------------------------------------------------------------------


def good_routes():
    secure = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'self'"}
    error = json.dumps({"error": {"code": "unauthorized", "message": "Sign in", "details": {}}})
    cors = {**secure, "Access-Control-Allow-Origin": APP_ORIGIN}
    return {
        ("GET", "/health"): (200, {}, json.dumps({"status": "ok"})),
        ("GET", "/ready"): (200, {}, json.dumps({"status": "ok", "postgres": "ok", "redis": "ok"})),
        ("GET", "/api/config"): (200, secure, json.dumps({"env": "staging", "beta_mode": True, "features": {"pulse": True}})),
        ("GET", "/api/openapi.json"): (200, {}, json.dumps({"paths": {"/api/config": {}}})),
        ("GET", "/api/me"): (401, {}, error),
        ("OPTIONS", "/api/me"): lambda handler: (
            200,
            cors if handler.headers.get("Origin") == APP_ORIGIN else secure,
            "",
        ),  # only the app
    }


@pytest.fixture
def stub():
    routes: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def respond(self):
            answer = routes.get((self.command, self.path), (404, {}, "{}"))
            status, headers, body = answer(self) if callable(answer) else answer
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body.encode())

        do_GET = do_OPTIONS = respond

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    routes.update(good_routes())
    routes["url"] = f"http://127.0.0.1:{server.server_port}"
    yield routes
    server.shutdown()


def check(stub, **kw):
    return run(stub["url"], kw.pop("origins", [APP_ORIGIN]), **kw)


def test_the_stub_baseline_passes(stub):
    code, text = check(stub)
    assert code == 0, text


def test_a_protected_endpoint_that_answers_without_a_token_fails(stub):
    stub[("GET", "/api/me")] = (200, {}, json.dumps({"id": 1}))
    code, text = check(stub)
    assert code == 1 and "FAIL  /api/me (no token)" in text


def test_a_protected_endpoint_with_a_non_standard_error_body_fails(stub):
    stub[("GET", "/api/me")] = (401, {}, "Unauthorized")
    assert check(stub)[0] == 1


def test_an_unknown_origin_that_is_allowed_fails(stub):
    stub[("OPTIONS", "/api/me")] = (200, {"Access-Control-Allow-Origin": "*"}, "")
    code, text = check(stub)
    assert code == 1 and f"FAIL  CORS {smoke.EVIL_ORIGIN}" in text and "FAIL  CORS http://localhost:3000" in text


def test_allowing_cookies_across_origins_fails(stub):
    stub[("OPTIONS", "/api/me")] = (
        200,
        {"Access-Control-Allow-Origin": APP_ORIGIN, "Access-Control-Allow-Credentials": "true"},
        "",
    )
    assert check(stub)[0] == 1


def test_a_failing_ready_check_fails(stub):
    stub[("GET", "/ready")] = (503, {}, json.dumps({"status": "fail", "postgres": "down"}))
    code, text = check(stub)
    assert code == 1 and "FAIL  /ready" in text and "DATABASE_URL" in text


def test_production_must_hide_the_api_description(stub):
    stub[("GET", "/api/config")] = (
        200,
        good_routes()[("GET", "/api/config")][1],
        json.dumps({"env": "production", "beta_mode": True, "features": {}}),
    )
    code, text = check(stub)
    assert code == 1 and "FAIL  /api/openapi.json" in text
    stub[("GET", "/api/openapi.json")] = (404, {}, "{}")
    assert check(stub)[0] == 0


def test_missing_security_headers_fail(stub):
    stub[("GET", "/api/config")] = (200, {}, json.dumps({"env": "staging", "beta_mode": True, "features": {}}))
    code, text = check(stub)
    assert code == 1 and "FAIL  nosniff" in text and "FAIL  CSP" in text


def test_a_malformed_config_fails(stub):
    stub[("GET", "/api/config")] = (200, {}, "<html>")
    assert check(stub)[0] == 1


def test_a_redirect_is_reported_not_followed(stub):
    stub[("GET", "/health")] = (301, {"Location": "https://elsewhere.example/health"}, "")
    code, text = check(stub)
    assert code == 1 and "FAIL  /health" in text and "got 301" in text


def test_no_origin_given_warns_and_still_checks_the_refusal(stub):
    code, text = check(stub, origins=[])
    assert code == 0 and "WARN  CORS" in text
