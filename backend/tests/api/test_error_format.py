"""Stage 6: unknown routes and server errors use our one error format in every environment except dev: no Django debug pages,
no stack traces, no exception text. (Django only uses its own error pages when DEBUG is on, and config refuses DEBUG outside dev.)"""

import json

import pytest
from django.test import Client
from django.urls import get_resolver

from core import errors

pytestmark = pytest.mark.django_db
SECRET = "SECRET-INTERNAL-DETAIL-do-not-leak"


class BoomMiddleware:
    """Raises on /boom, outside the API router, the way a bug in a middleware would."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info == "/boom":
            raise RuntimeError(SECRET)
        return self.get_response(request)


def standard(response, status, code):
    assert response.status_code == status, response.content[:200]
    assert response["Content-Type"].startswith("application/json")
    body = json.loads(response.content)
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "details"} and body["error"]["code"] == code
    text = response.content.decode()
    assert "<html" not in text.lower() and "Traceback" not in text and SECRET not in text and "/home/" not in text
    return body


def test_an_unknown_api_path_is_a_standard_404():
    standard(Client().get("/api/this-does-not-exist"), 404, "not_found")


def test_an_unknown_path_outside_the_api_is_a_standard_404_not_a_django_page():
    for path in ("/", "/nothing-here", "/wp-admin/setup.php", "/static/x.js"):
        standard(Client().get(path), 404, "not_found")


def test_the_wrong_method_on_a_real_route_is_a_standard_405_with_allow(make_member, client_for):
    r = client_for(make_member("student")).delete("/api/me")
    body = standard(r, 405, "method_not_allowed")
    assert "GET" in r["Allow"] and "PATCH" in r["Allow"] and body["error"]["message"]
    standard(Client().put("/api/health"), 405, "method_not_allowed")  # also for public routes, signed out


def test_the_405_keeps_the_security_and_cors_headers(settings):
    settings.CORS_ALLOWED_ORIGINS = ["https://app.example"]
    r = Client().put("/api/health", HTTP_ORIGIN="https://app.example")
    assert r.status_code == 405 and r["X-Content-Type-Options"] == "nosniff"
    assert r["Access-Control-Allow-Origin"] == "https://app.example"  # innermost middleware: the headers are still added


def test_an_unexpected_error_inside_an_endpoint_is_a_standard_500(make_member, client_for, monkeypatch):
    from apps.accounts import api as accounts_api

    def boom(*a, **kw):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(accounts_api, "_me", boom)
    standard(client_for(make_member("student")).get("/api/me"), 500, "internal_error")


def test_an_error_in_a_middleware_outside_the_api_is_a_standard_500(settings):
    settings.MIDDLEWARE = [*settings.MIDDLEWARE, "tests.api.test_error_format.BoomMiddleware"]
    r = Client(raise_request_exception=False).get("/boom")
    standard(r, 500, "internal_error")
    r = Client(raise_request_exception=False).get("/api/health")  # the app is still fine for everything else
    assert r.status_code == 200


def test_the_error_is_logged_without_leaking_to_the_client(make_member, client_for, monkeypatch, capfd):
    from apps.accounts import api as accounts_api

    monkeypatch.setattr(accounts_api, "_me", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError(SECRET)))
    r = client_for(make_member("student")).get("/api/me")
    assert SECRET not in r.content.decode()
    assert "unhandled" in capfd.readouterr().out  # the team sees it in the logs, the client does not


def test_django_is_pointed_at_our_handlers():
    resolver = get_resolver()
    for status, name in ((400, "handler400"), (403, "handler403"), (404, "handler404"), (500, "handler500")):
        callback = resolver.resolve_error_handler(status)
        assert callback is getattr(errors, name), status


def test_the_other_handlers_answer_in_the_standard_format(rf):
    standard(errors.handler403(rf.get("/")), 403, "forbidden")
    standard(errors.handler400(rf.get("/")), 400, "bad_request")


def test_validation_errors_are_still_standard(make_member, client_for):
    body = standard(client_for(make_member("student")).get("/api/posts/not-a-number"), 422, "validation_error")
    assert isinstance(body["error"]["details"], list)
