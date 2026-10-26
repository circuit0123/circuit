"""F18: with BETA_MODE on, a signed-in member without access is stopped in ONE place (SupabaseAuth), for every route."""

import pytest
from django.test import Client

from apps.beta.models import AllowlistEntry, BetaAccess, WaitlistEntry
from tests.api.test_access_matrix import MATRIX, PUBLIC, call, operations

pytestmark = pytest.mark.django_db

# The only protected routes a member without access may use: who am I, redeem a code, onboarding helpers, accept the policy,
# and the privacy rights (export, delete, write to support), which never depend on holding an invite.
OPEN_TO_MEMBERS_WITHOUT_ACCESS = {
    ("GET", "/api/me"),
    ("POST", "/api/beta/redeem"),
    ("POST", "/api/onboarding/extract"),
    ("GET", "/api/onboarding/state"),
    ("PATCH", "/api/onboarding/state"),
    ("POST", "/api/me/consent"),
    ("GET", "/api/me/export"),
    ("POST", "/api/me/export"),
    ("GET", "/api/me/export/download"),
    ("POST", "/api/me/deletion"),
    ("POST", "/api/support"),
}


def gated(response):
    return response.status_code == 403 and response.json()["error"]["code"] == "beta_required"


def test_every_other_route_is_gated_and_only_the_exempt_ones_are_not(beta_on, make_member, client_for):
    """Loops over every operation in the OpenAPI schema, so a new endpoint is covered the day it is added."""
    ops = operations()
    assert ops - PUBLIC == set(MATRIX), "the matrix and the schema disagree; fix tests/api/test_access_matrix.py first"
    # a fresh member per route: one of the routes deletes the account, which would lock out every later call
    not_gated = {op for op in sorted(ops - PUBLIC) if not gated(call(client_for(make_member("student")), *op))}
    assert not_gated == OPEN_TO_MEMBERS_WITHOUT_ACCESS


def test_gated_answer_uses_the_standard_error_format(beta_on, make_member, client_for):
    r = client_for(make_member("student")).get("/api/matches")
    assert r.status_code == 403
    assert r.json() == {"error": {"code": "beta_required", "message": r.json()["error"]["message"], "details": None}}


def test_public_routes_stay_open_without_a_token(beta_on):
    needs_input = {
        ("POST", "/api/demo/token"),
        ("POST", "/api/waitlist"),
        ("POST", "/api/join/visit"),
        ("GET", "/api/unsubscribe"),
        ("POST", "/api/unsubscribe"),
    }
    for method, path in sorted(PUBLIC - needs_input):
        assert Client().generic(method, path).status_code in (200, 404), path


def test_beta_mode_off_means_no_gate(make_member, client_for):
    outsider = make_member("student")
    for op in sorted(MATRIX):
        r = call(client_for(outsider), *op)
        assert not gated(r), op


def test_a_member_with_access_gets_through(beta_on, make_member, client_for, let_in):
    m = make_member("student")
    let_in(m)
    assert client_for(m).get("/api/matches").status_code == 200


def test_revoked_access_is_locked_out_even_with_an_allowlisted_email(beta_on, make_member, client_for, let_in):
    from django.utils import timezone

    m = make_member("student")
    access = let_in(m)
    AllowlistEntry.objects.create(email="someone@example.org")
    access.revoked_at = timezone.now()
    access.save()
    assert gated(client_for(m).get("/api/matches"))


@pytest.mark.parametrize("role", ["partner_admin", "super_admin"])
def test_admins_appointed_by_circuit_are_not_gated(beta_on, role, make_member, make_org, client_for):
    m = make_member(role, org=make_org())
    assert client_for(m).get("/api/me/needs").status_code == 200


def test_a_revoked_admin_is_gated_too(beta_on, make_member, make_org, client_for, let_in):
    from django.utils import timezone

    m = make_member("partner_admin", org=make_org())
    access = let_in(m)
    access.revoked_at = timezone.now()
    access.save()
    assert gated(client_for(m).get("/api/me/needs"))


# -- beta_access on /api/me and /api/config ------------------------------------------------------------
def test_me_and_config_say_whether_the_member_is_in(beta_on, make_member, client_for, let_in):
    m = make_member("student")
    c = client_for(m)
    assert c.get("/api/me").json()["beta_access"] is False
    cfg = c.get("/api/config").json()
    assert cfg["beta_mode"] is True and cfg["beta_access"] is False
    let_in(m)
    assert c.get("/api/me").json()["beta_access"] is True
    assert c.get("/api/config").json()["beta_access"] is True


def test_config_for_an_anonymous_visitor(settings, client_for):
    settings.BETA_MODE = True
    assert client_for().get("/api/config").json()["beta_access"] is False
    settings.BETA_MODE = False
    assert client_for().get("/api/config").json()["beta_access"] is True


def test_me_says_true_when_the_beta_is_off(make_member, client_for):
    assert client_for(make_member("student")).get("/api/me").json()["beta_access"] is True


def test_config_with_a_bad_token_is_anonymous_not_an_error(beta_on, client_for):
    r = client_for().get("/api/config", HTTP_AUTHORIZATION="Bearer nope")
    assert r.status_code == 200 and r.json()["beta_access"] is False


def test_config_never_trips_the_gate_for_a_member_without_access(beta_on, make_member, client_for):
    assert client_for(make_member("student")).get("/api/config").status_code == 200


# -- the allowlist and approved waitlist use the VERIFIED sign-in email only ------------------------------------
def test_allowlisted_verified_email_gets_in_and_is_remembered(beta_on, make_member, client_for):
    AllowlistEntry.objects.create(email="friend@example.org")
    m = make_member("student")
    c = client_for(m, email="Friend@Example.org")  # sign-in providers may change the case
    assert c.get("/api/matches").status_code == 200
    assert BetaAccess.objects.get(member=m).source == "allowlist"
    AllowlistEntry.objects.all().delete()
    assert c.get("/api/matches").status_code == 200  # access is a row now, not a lookup


def test_allowlist_ignores_an_email_the_provider_did_not_verify(beta_on, make_member, client_for):
    AllowlistEntry.objects.create(email="friend@example.org")
    m = make_member("student")
    c = client_for(m, email="friend@example.org", app_metadata={"provider": "github"})
    assert gated(c.get("/api/matches"))
    assert not BetaAccess.objects.filter(member=m).exists()


def test_allowlist_ignores_an_email_in_user_metadata(beta_on, make_member, client_for):
    """user_metadata is editable by the user; only the signed `email` claim from a verified provider counts."""
    AllowlistEntry.objects.create(email="friend@example.org")
    m = make_member("student")
    c = client_for(m, email="stranger@example.org", user_metadata={"email": "friend@example.org"})
    assert gated(c.get("/api/matches"))


def test_allowlist_ignores_an_email_the_client_sends_in_the_request(beta_on, make_member, client_for):
    AllowlistEntry.objects.create(email="friend@example.org")
    m = make_member("student")
    c = client_for(m, email="stranger@example.org")
    assert gated(c.get("/api/matches?email=friend@example.org", HTTP_X_EMAIL="friend@example.org"))
    assert gated(c.post("/api/organisations/join-by-email", {"email": "friend@example.org"}))


def test_allowlist_never_matches_a_demo_token(beta_on, settings, make_member):
    from core import auth

    settings.DEMO_AUTH = True
    AllowlistEntry.objects.create(email="friend@example.org")
    m = make_member("student")
    token = auth.issue_demo_token(m.auth_user_id)
    assert gated(Client(HTTP_AUTHORIZATION=f"Bearer {token}").get("/api/matches"))


def test_allowlist_rejects_lookalike_unicode_email(beta_on, make_member, client_for):
    AllowlistEntry.objects.create(email="kim@example.org")
    m = make_member("student")
    c = client_for(m, email="Kim@example.org")  # Kelvin sign: lower-cases to a plain k
    assert gated(c.get("/api/matches"))


def test_approved_waitlist_email_gets_in(beta_on, make_member, client_for):
    WaitlistEntry.objects.create(email="wait@example.org", role="student", status="approved")
    WaitlistEntry.objects.create(email="pending@example.org", role="student")
    ok, no = make_member("student"), make_member("student")
    assert client_for(ok, email="wait@example.org").get("/api/matches").status_code == 200
    assert BetaAccess.objects.get(member=ok).source == "approved"
    assert gated(client_for(no, email="pending@example.org").get("/api/matches"))
