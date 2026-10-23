"""Every route x every role. Stage 3 endpoints MUST be added here: the meta-test fails otherwise."""

import pytest
from django.test import Client

from circuit.api import api

pytestmark = pytest.mark.django_db

ROLES = ["student", "founder", "mentor", "investor", "partner_admin", "super_admin"]
JOINABLE = ["student", "founder", "mentor", "investor"]

# Routes that need no token. Anything else must answer 401 to an anonymous caller.
PUBLIC = {("GET", "/api/health"), ("GET", "/api/health/deps"), ("GET", "/api/demo/personas"), ("POST", "/api/demo/token")}


def by_role(default=403, **over):
    return {**{r: default for r in ROLES}, **over}


# (method, path) -> expected status per role, for a member who belongs to an organisation.
MATRIX = {
    ("GET", "/api/me"): by_role(200),
    ("GET", "/api/organisations/mine"): by_role(200),
    ("POST", "/api/organisations/join"): by_role(403, **{r: 409 for r in JOINABLE}),
    ("POST", "/api/organisations/join-by-email"): by_role(403, **{r: 409 for r in JOINABLE}),
    ("POST", "/api/organisations/leave"): by_role(204, partner_admin=403),
    ("GET", "/api/organisations/mine/members"): by_role(403, partner_admin=200),
    ("DELETE", "/api/organisations/mine/members/{member_id}"): by_role(403, partner_admin=404),
    # Stage 3, part 1
    ("PATCH", "/api/me"): by_role(200),
    ("GET", "/api/capabilities"): by_role(200),
    ("GET", "/api/traits"): by_role(200),
    ("GET", "/api/me/needs"): by_role(200),
    ("PUT", "/api/me/needs"): by_role(200),
    ("GET", "/api/me/offers"): by_role(200),
    ("PUT", "/api/me/offers"): by_role(200),
    ("GET", "/api/me/skills"): by_role(200),
    ("PUT", "/api/me/skills"): by_role(200),
    ("GET", "/api/me/traits"): by_role(200),
    ("PUT", "/api/me/traits"): by_role(200),
    ("GET", "/api/members/{member_id}"): by_role(404),
    ("POST", "/api/onboarding/extract"): by_role(200),
    ("POST", "/api/me/verify/work-email"): by_role(200),
    ("POST", "/api/me/verify/work-email/confirm"): by_role(400),
    ("GET", "/api/startups/nearby"): by_role(200),
    ("GET", "/api/startups/map"): by_role(200),
    ("GET", "/api/startups/{startup_id}"): by_role(404),
    ("PATCH", "/api/startups/{startup_id}"): by_role(404),
    ("POST", "/api/startups/{startup_id}/interest"): by_role(403, student=404),
    ("DELETE", "/api/startups/{startup_id}/interest"): by_role(403, student=404),
    ("POST", "/api/startups/{startup_id}/claim"): by_role(403, founder=404),
    ("POST", "/api/startups/{startup_id}/claim/verify"): by_role(403, founder=404),
    # Stage 3, part 2: jobs, applications, notifications
    ("GET", "/api/jobs"): by_role(200),
    ("GET", "/api/jobs/{job_id}"): by_role(404),
    ("POST", "/api/jobs"): by_role(403, founder=404),
    ("PATCH", "/api/jobs/{job_id}"): by_role(403, founder=404),
    ("POST", "/api/jobs/{job_id}/apply"): by_role(403, student=404),
    ("GET", "/api/jobs/{job_id}/applicants"): by_role(403, founder=404),
    ("GET", "/api/me/applications"): by_role(403, student=200),
    ("POST", "/api/applications/{application_id}/withdraw"): by_role(403, student=404),
    ("PATCH", "/api/applications/{application_id}"): by_role(403, founder=404),
    ("GET", "/api/matches"): by_role(200),
    ("GET", "/api/notifications"): by_role(200),
    ("GET", "/api/notifications/unread-count"): by_role(200),
    ("POST", "/api/notifications/read-all"): by_role(200),
    ("POST", "/api/notifications/{notification_id}/read"): by_role(404),
}

# Request bodies and query strings for routes that need them (default POST body is {"code": "X"}).
BODIES = {
    ("PATCH", "/api/me"): "{}",
    ("PUT", "/api/me/needs"): "[]",
    ("PUT", "/api/me/offers"): "[]",
    ("PUT", "/api/me/skills"): "[]",
    ("PUT", "/api/me/traits"): "[]",
    ("PATCH", "/api/startups/{startup_id}"): "{}",
    ("POST", "/api/onboarding/extract"): '{"bio": "I build things and need help with sales."}',
    ("POST", "/api/me/verify/work-email"): '{"email": "someone@acme.io"}',
    ("POST", "/api/me/verify/work-email/confirm"): '{"code": "ABCDEFGH"}',
    ("POST", "/api/startups/{startup_id}/claim"): '{"email": "me@acme.io"}',
    ("POST", "/api/startups/{startup_id}/claim/verify"): '{"code": "ABCDEFGH"}',
    ("POST", "/api/jobs"): '{"startup_id": 999999, "title": "Intern", "capabilities": [{"capability": "seo"}]}',
    ("PATCH", "/api/jobs/{job_id}"): "{}",
    ("PATCH", "/api/applications/{application_id}"): '{"status": "shortlisted"}',
}
QUERIES = {("GET", "/api/startups/map"): "?min_lng=80&min_lat=13&max_lng=80.5&max_lat=13.5"}


def call(client, method, path):
    key = (method, path)
    url = path
    for name in ("member_id", "startup_id", "job_id", "application_id", "notification_id"):
        url = url.replace("{" + name + "}", "999999")
    url += QUERIES.get(key, "")
    body = BODIES.get(key, '{"code": "X"}' if method == "POST" else None)
    return client.generic(method, url, body, content_type="application/json") if body else client.generic(method, url)


def operations():
    return {(m.upper(), p) for p, item in api.get_openapi_schema()["paths"].items() for m in item}


def test_every_route_is_in_the_matrix_or_public():
    ops = operations()
    missing = ops - set(MATRIX) - PUBLIC
    assert not missing, f"add these routes to the access matrix: {sorted(missing)}"
    assert not (set(MATRIX) | PUBLIC) - ops, "matrix lists routes that no longer exist"


def test_only_public_routes_skip_auth():
    schema = api.get_openapi_schema()["paths"]
    open_routes = {(m.upper(), p) for p, item in schema.items() for m, op in item.items() if not op.get("security")}
    assert open_routes == PUBLIC


@pytest.mark.parametrize("route", sorted(MATRIX))
def test_anonymous_gets_401(route):
    r = call(Client(), *route)
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


@pytest.mark.parametrize("route", sorted(MATRIX))
@pytest.mark.parametrize("role", ROLES)
def test_each_role_on_each_route(route, role, make_member, make_org, client_for):
    member = make_member(role, org=make_org())
    r = call(client_for(member), *route)
    assert r.status_code == MATRIX[route][role], f"{role} {route}: {r.status_code} {r.content[:200]!r}"
    if r.status_code >= 400:
        assert set(r.json()["error"]) == {"code", "message", "details"}  # one error format everywhere
