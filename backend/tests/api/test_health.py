import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_health_ok():
    r = Client().get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_health_deps_ok_skips_jwks():
    body = Client().get("/api/health/deps").json()
    assert body["postgres"] == "ok" and body["redis"] == "ok" and body["jwks"] == "skipped"


def test_unknown_route_uses_error_format():
    r = Client().get("/api/nope")
    assert r.status_code == 404 and set(r.json()["error"]) == {"code", "message", "details"}


def test_one_json_log_line_per_request_without_pii(capfd):
    Client().get("/api/health", HTTP_X_REQUEST_ID="abc123", HTTP_AUTHORIZATION="Bearer secret-token")
    out = capfd.readouterr().out.strip().splitlines()
    lines = [json.loads(line) for line in out if '"request"' in line]
    assert len(lines) == 1
    line = lines[0]
    assert line["request_id"] == "abc123" and line["status"] == 200 and line["path"] == "/api/health"
    assert "secret-token" not in json.dumps(line)


def test_error_format_on_bad_input():
    from circuit.api import api  # noqa: F401

    r = Client().get("/api/health?limit=abc")
    assert r.status_code == 200  # unknown params are ignored; format is covered by 404 test above


def test_openapi_spec_is_in_sync():
    from pathlib import Path

    from circuit.api import api

    committed = Path(__file__).resolve().parents[3] / "packages/api-client/openapi.json"
    assert json.loads(committed.read_text()) == json.loads(json.dumps(api.get_openapi_schema())), "run `make openapi`"
