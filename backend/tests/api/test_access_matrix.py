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
}


def call(client, method, path):
    path = path.replace("{member_id}", "999999")
    body = '{"code": "X"}' if method == "POST" else None
    return client.generic(method, path, body, content_type="application/json") if body else client.generic(method, path)


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
