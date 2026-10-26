"""/health and /ready (core.health.ProbeMiddleware) and the Cloud Logging fields (core.logging)."""

import json
import logging

import pytest
from django.db import connection
from django.test import Client

from core import cache as cache_module

BAD_HOST = {"HTTP_HOST": "10.1.2.3:8080"}  # what a platform probe sends: the container's own address, not our domain


def json_lines(capfd):
    return [json.loads(line) for line in capfd.readouterr().out.splitlines() if line.startswith("{")]


# ---- /health -----------------------------------------------------------------------------------------------------------


def test_health_answers_with_any_host_and_touches_no_database():
    # no django_db mark on this test: any query would raise, which proves /health asks nothing of Postgres
    r = Client().get("/health", **BAD_HOST)
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert r["Cache-Control"] == "no-store"
    assert Client().get("/api/health", **BAD_HOST).status_code == 400  # the normal API still refuses an unknown host


def test_health_answers_head_and_leaves_other_methods_to_the_api():
    assert Client().head("/health", **BAD_HOST).status_code == 200
    assert Client().post("/health").status_code in (404, 405)


def test_health_works_over_plain_http_even_where_everything_else_redirects_to_https(settings):
    settings.SECURE_SSL_REDIRECT = True
    r = Client().get("/health", **BAD_HOST)
    assert r.status_code == 200


# ---- /ready ------------------------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_ready_reports_postgres_and_redis():
    r = Client().get("/ready", **BAD_HOST)
    assert r.status_code == 200 and r.json() == {"status": "ok", "postgres": "ok", "redis": "ok"}


@pytest.mark.django_db
def test_redis_down_is_a_warning_not_a_failure(monkeypatch, capfd):
    monkeypatch.setattr(cache_module.Cache, "ping", lambda self: False)
    r = Client().get("/ready", **BAD_HOST)
    assert r.status_code == 200
    assert r.json() == {"status": "degraded", "postgres": "ok", "redis": "down"}
    warnings = [line for line in json_lines(capfd) if line.get("event") == "ready.degraded"]
    assert warnings and warnings[0]["severity"] == "WARNING"


@pytest.mark.django_db
def test_postgres_down_fails_ready_with_503_and_logs_an_error(monkeypatch, capfd):
    def broken(*a, **k):
        raise RuntimeError("connection to server at db.internal.example failed")

    monkeypatch.setattr(connection, "cursor", broken)
    r = Client().get("/ready", **BAD_HOST)
    assert r.status_code == 503
    assert r.json() == {"status": "fail", "postgres": "down"}
    assert "internal" not in r.content.decode()  # the reason goes to the log, never to whoever asked
    errors = [line for line in json_lines(capfd) if line.get("event") == "ready.failed"]
    assert errors and errors[0]["severity"] == "ERROR" and errors[0]["error"] == "RuntimeError"


@pytest.mark.django_db
def test_probes_do_not_write_request_log_lines_but_api_requests_do(capfd):
    for _ in range(3):
        Client().get("/health", **BAD_HOST)
        Client().get("/ready", **BAD_HOST)
    assert [line for line in json_lines(capfd) if line.get("event") == "request"] == []
    Client().get("/api/health")
    assert len([line for line in json_lines(capfd) if line.get("event") == "request"]) == 1


# ---- Cloud Logging fields ------------------------------------------------------------------------------------------------


def test_every_log_line_has_a_severity_and_a_message(capfd):
    Client().get("/api/health")
    line = next(line for line in json_lines(capfd) if line.get("event") == "request")
    assert line["severity"] == "INFO" and line["message"] == "request"
    assert line["level"] == "info"  # our own field stays


@pytest.mark.parametrize(
    "level, severity",
    [
        ("debug", "DEBUG"),
        ("info", "INFO"),
        ("warning", "WARNING"),
        ("error", "ERROR"),
        ("critical", "CRITICAL"),
        ("exception", "ERROR"),
    ],
)
def test_severity_mapping(level, severity):
    from core.logging import cloud_logging

    assert cloud_logging(None, level, {"level": level, "event": "x"})["severity"] == severity


def test_trace_id_links_log_lines_to_cloud_trace_when_the_project_is_known(settings, capfd):
    settings.GOOGLE_CLOUD_PROJECT = "circuit-test-1"
    trace = "105445aa7843bc8bf206b12000100000"
    Client().get("/api/health", HTTP_X_CLOUD_TRACE_CONTEXT=f"{trace}/1;o=1")
    line = next(line for line in json_lines(capfd) if line.get("event") == "request")
    assert line["logging.googleapis.com/trace"] == f"projects/circuit-test-1/traces/{trace}"


def test_no_trace_field_without_a_project_or_a_header(settings, capfd):
    settings.GOOGLE_CLOUD_PROJECT = ""
    Client().get("/api/health", HTTP_X_CLOUD_TRACE_CONTEXT="105445aa7843bc8bf206b12000100000/1;o=1")
    settings.GOOGLE_CLOUD_PROJECT = "circuit-test-1"
    Client().get("/api/health", HTTP_X_CLOUD_TRACE_CONTEXT="not-a-trace")
    assert not any("logging.googleapis.com/trace" in line for line in json_lines(capfd))


def test_django_and_gunicorn_log_lines_are_json_with_a_severity_and_the_traceback():
    from core.logging import StdlibJsonFormatter

    fmt = StdlibJsonFormatter()
    plain = logging.LogRecord("django.request", logging.WARNING, __file__, 1, "Not Found: %s", ("/x",), None)
    assert json.loads(fmt.format(plain)) == {"severity": "WARNING", "message": "Not Found: /x", "logger": "django.request"}
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        crash = logging.LogRecord("django.request", logging.ERROR, __file__, 1, "Internal Server Error", (), sys.exc_info())
    out = json.loads(fmt.format(crash))
    assert out["severity"] == "ERROR" and "Traceback" in out["message"] and "ValueError: boom" in out["message"]


def test_gunicorn_logs_to_stdout_in_the_same_format():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("g", Path(__file__).resolve().parents[2] / "circuit/gunicorn.py")
    conf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conf)
    cfg = conf.logconfig_dict
    assert cfg["handlers"]["console"]["stream"] == "ext://sys.stdout"
    assert cfg["formatters"]["json"]["()"] == "core.logging.StdlibJsonFormatter"
    assert cfg["loggers"]["gunicorn.error"]["handlers"] == ["console"]
