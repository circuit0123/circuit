"""Every route x every role. Stage 3 endpoints MUST be added here: the meta-test fails otherwise."""

import pytest
from django.test import Client

from circuit.api import api

pytestmark = pytest.mark.django_db

ROLES = ["student", "founder", "mentor", "investor", "partner_admin", "super_admin"]
JOINABLE = ["student", "founder", "mentor", "investor"]

# Routes that need no token. Anything else must answer 401 to an anonymous caller.
PUBLIC = {
    ("GET", "/api/config"),
    ("GET", "/api/health"),
    ("GET", "/api/health/deps"),
    ("GET", "/api/demo/personas"),
    ("POST", "/api/demo/token"),
    ("POST", "/api/waitlist"),
}


def by_role(default=403, **over):
    return {**{r: default for r in ROLES}, **over}


def social(status):
    """Network roles get `status`; partner and super admins are not part of the social network (403)."""
    return by_role(403, **{r: status for r in JOINABLE})


def messaging(status):
    """Messaging also admits partner admins (they may message their own organisation, including under-18s)."""
    return by_role(403, **{r: status for r in [*JOINABLE, "partner_admin"]})


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
    # Stage 3, part 4: intros (admins have no intros; everyone else is checked against an id that does not exist)
    ("GET", "/api/intros/path/{target_id}"): by_role(403, **{r: 404 for r in JOINABLE}),
    ("POST", "/api/intros"): by_role(403, **{r: 404 for r in JOINABLE}),
    ("GET", "/api/intros"): by_role(403, **{r: 200 for r in JOINABLE}),
    ("POST", "/api/intros/{intro_id}/respond"): by_role(403, **{r: 404 for r in JOINABLE}),
    ("POST", "/api/intros/{intro_id}/rating"): by_role(403, **{r: 404 for r in JOINABLE}),
    ("GET", "/api/dashboard/gaps"): by_role(403, partner_admin=200),
    ("GET", "/api/dashboard/heatmap"): by_role(403, partner_admin=200),
    ("GET", "/api/dashboard/network"): by_role(403, partner_admin=200),
    ("GET", "/api/dashboard/acceptance"): by_role(403, partner_admin=200),
    ("GET", "/api/circuits"): by_role(403, **{r: 200 for r in JOINABLE}),
    ("GET", "/api/circuits/{circuit_id}"): by_role(403, **{r: 404 for r in JOINABLE}),
    ("POST", "/api/circuits/{circuit_id}/respond"): by_role(403, **{r: 404 for r in JOINABLE}),
    ("POST", "/api/circuits/{circuit_id}/legs/{leg_id}/done"): by_role(403, **{r: 404 for r in JOINABLE}),
    ("POST", "/api/circuits/{circuit_id}/legs/{leg_id}/rating"): by_role(403, **{r: 404 for r in JOINABLE}),
    ("GET", "/api/notifications"): by_role(200),
    ("GET", "/api/notifications/unread-count"): by_role(200),
    ("POST", "/api/notifications/read-all"): by_role(200),
    ("POST", "/api/notifications/{notification_id}/read"): by_role(404),
    # Stage 3b: social (F15-F17)
    ("POST", "/api/media/uploads"): social(201),
    ("POST", "/api/media/uploads/{upload_id}/complete"): by_role(404),
    ("POST", "/api/posts"): social(201),
    ("GET", "/api/posts/{post_id}"): social(404),
    ("DELETE", "/api/posts/{post_id}"): by_role(404),
    ("GET", "/api/members/{member_id}/posts"): social(404),
    ("PUT", "/api/posts/{post_id}/reactions/{kind}"): social(404),
    ("DELETE", "/api/posts/{post_id}/reactions/{kind}"): social(404),
    ("GET", "/api/posts/{post_id}/replies"): social(404),
    ("POST", "/api/posts/{post_id}/replies"): social(404),
    ("DELETE", "/api/replies/{reply_id}"): by_role(404),
    ("GET", "/api/pulse"): social(200),
    ("POST", "/api/pulse/seen"): social(204),
    ("GET", "/api/livewire"): social(200),
    ("POST", "/api/livewire/seen"): social(404),
    ("GET", "/api/drop/today"): social(200),
    ("POST", "/api/drop/today/{member_id}/swipe"): social(404),
    ("POST", "/api/startups/{startup_id}/follow"): social(404),
    ("DELETE", "/api/startups/{startup_id}/follow"): social(204),
    ("GET", "/api/me/follows"): social(200),
    ("GET", "/api/connections"): social(200),
    ("DELETE", "/api/connections/{member_id}"): social(404),
    ("POST", "/api/connections/requests"): social(404),
    ("GET", "/api/connections/requests"): social(200),
    ("POST", "/api/connections/requests/{request_id}/respond"): social(404),
    ("GET", "/api/conversations"): messaging(200),
    ("POST", "/api/conversations"): messaging(404),
    ("GET", "/api/conversations/{conversation_id}"): messaging(404),
    ("GET", "/api/conversations/{conversation_id}/messages"): messaging(404),
    ("GET", "/api/conversations/{conversation_id}/messages/{message_id}"): messaging(404),
    ("POST", "/api/conversations/{conversation_id}/messages"): messaging(404),
    ("POST", "/api/conversations/{conversation_id}/accept"): messaging(404),
    ("POST", "/api/conversations/{conversation_id}/block"): messaging(404),
    ("POST", "/api/conversations/{conversation_id}/read"): messaging(404),
    ("POST", "/api/reports"): by_role(404, super_admin=403),
    # Stage 4b: invite-only beta (F18). BETA_MODE is off here; tests/api/test_beta_gate.py covers the gate itself.
    ("GET", "/api/invites"): by_role(200),
    ("POST", "/api/beta/redeem"): by_role(400),  # "X" is not a code, for anyone
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
    ("POST", "/api/intros"): '{"target_id": 999999}',
    ("POST", "/api/intros/{intro_id}/respond"): '{"accept": true}',
    ("POST", "/api/intros/{intro_id}/rating"): '{"rating": 3}',
    ("POST", "/api/circuits/{circuit_id}/respond"): '{"accept": true}',
    ("POST", "/api/circuits/{circuit_id}/legs/{leg_id}/rating"): '{"rating": 3}',
    ("PATCH", "/api/jobs/{job_id}"): "{}",
    ("PATCH", "/api/applications/{application_id}"): '{"status": "shortlisted"}',
    ("POST", "/api/media/uploads"): '{"purpose": "post", "content_type": "image/png", "size": 1000}',
    ("POST", "/api/posts"): '{"body": "Shipped the first version", "visibility": "organisation"}',
    ("POST", "/api/posts/{post_id}/replies"): '{"body": "Nice work"}',
    ("POST", "/api/livewire/seen"): '{"key": "post:999999"}',
    ("POST", "/api/drop/today/{member_id}/swipe"): '{"direction": "skip"}',
    ("POST", "/api/connections/requests"): '{"member_id": 999999, "note": ""}',
    ("POST", "/api/connections/requests/{request_id}/respond"): '{"accept": true}',
    ("POST", "/api/conversations"): '{"member_id": 999999, "body": "Hi"}',
    ("POST", "/api/conversations/{conversation_id}/messages"): '{"body": "Hi"}',
    ("POST", "/api/reports"): '{"target_type": "post", "target_id": 999999, "reason": "spam"}',
}
QUERIES = {("GET", "/api/startups/map"): "?min_lng=80&min_lat=13&max_lng=80.5&max_lat=13.5"}


def call(client, method, path):
    key = (method, path)
    url = path
    for name in (
        "member_id",
        "startup_id",
        "job_id",
        "application_id",
        "notification_id",
        "target_id",
        "intro_id",
        "circuit_id",
        "leg_id",
        "post_id",
        "reply_id",
        "upload_id",
        "request_id",
        "conversation_id",
        "message_id",
    ):
        url = url.replace("{" + name + "}", "999999")
    url = url.replace("{kind}", "helpful")
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
