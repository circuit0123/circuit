import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

ORIGIN = "https://circuit-app-staging.vercel.app"
PREVIEW = r"^https://circuit-app-staging-git-.*\.vercel\.app$"


@pytest.fixture(autouse=True)
def cors(settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.CORS_ALLOWED_ORIGIN_REGEXES = [PREVIEW]


def acao(response):
    return response.headers.get("Access-Control-Allow-Origin")


def test_exact_origin_allowed():
    assert acao(Client().get("/api/health", HTTP_ORIGIN=ORIGIN)) == ORIGIN


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        ORIGIN + ".evil.example",
        "http://circuit-app-staging.vercel.app",  # wrong scheme
        "https://circuit-app-staging-git-x.vercel.app.evil.example",  # regex must be anchored
        "https://evil.example/https://circuit-app-staging-git-x.vercel.app",
        "null",
    ],
)
def test_other_origins_denied(origin):
    r = Client().get("/api/health", HTTP_ORIGIN=origin)
    assert acao(r) is None


def test_preview_regex_allows_vercel_previews():
    origin = "https://circuit-app-staging-git-feature-x-team.vercel.app"
    assert acao(Client().get("/api/health", HTTP_ORIGIN=origin)) == origin


def test_no_preview_regex_in_production_style_config(settings):
    settings.CORS_ALLOWED_ORIGIN_REGEXES = []
    assert acao(Client().get("/api/health", HTTP_ORIGIN="https://circuit-app-staging-git-x.vercel.app")) is None


def preflight(origin):
    return Client().options(
        "/api/organisations/join",
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
    )


def test_preflight_ok_for_allowed_origin():
    r = preflight(ORIGIN)
    assert r.status_code == 200 and acao(r) == ORIGIN
    assert "authorization" in r.headers["Access-Control-Allow-Headers"].lower()
    assert "POST" in r.headers["Access-Control-Allow-Methods"]


def test_preflight_gets_no_allow_headers_for_other_origin():
    assert acao(preflight("https://evil.example")) is None


def test_credentials_are_never_allowed():
    assert "Access-Control-Allow-Credentials" not in Client().get("/api/health", HTTP_ORIGIN=ORIGIN).headers


def test_security_headers_present():
    h = Client().get("/api/health").headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "same-origin"
    assert h["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "frame-ancestors 'none'" in h["Content-Security-Policy"] and "default-src 'self'" in h["Content-Security-Policy"]


def test_security_headers_also_on_errors():
    h = Client().get("/api/nope").headers
    assert h["X-Content-Type-Options"] == "nosniff" and "Content-Security-Policy" in h


def test_oversized_body_is_413_in_standard_format(make_member, client_for):
    r = client_for(make_member()).post("/api/organisations/join", json.dumps({"code": "A" * 2_000_000}))
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"
