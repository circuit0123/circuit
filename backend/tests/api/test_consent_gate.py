"""Stage 7: consent with a policy version. A member who has not accepted the CURRENT version gets 403 `consent_required` everywhere
except a short list, enforced in the one place the beta gate lives (core/gate.py, called from SupabaseAuth.authenticate)."""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.models import Consent
from tests.api.test_access_matrix import MATRIX, PUBLIC, call, operations

pytestmark = pytest.mark.django_db

# The only protected routes a member who has not accepted the current policy may use.
OPEN_WITHOUT_CONSENT = {
    ("GET", "/api/me"),
    ("POST", "/api/me/consent"),
    ("GET", "/api/me/export"),
    ("POST", "/api/me/export"),
    ("GET", "/api/me/export/download"),
    ("POST", "/api/me/deletion"),
    ("POST", "/api/support"),
}


def refused(response):
    return response.status_code == 403 and response.json()["error"]["code"] == "consent_required"


def accept(member, version="2026-01", days_ago=0):
    return Consent.objects.create(member=member, policy_version=version, accepted_at=timezone.now() - timedelta(days=days_ago))


def test_every_route_but_the_exempt_ones_needs_consent(consent_on, make_member, client_for):
    """Loops over every operation in the OpenAPI schema, so a new endpoint is covered the day it is added."""
    ops = operations()
    assert ops - PUBLIC == set(MATRIX), "the matrix and the schema disagree; fix tests/api/test_access_matrix.py first"
    open_routes = {op for op in sorted(ops - PUBLIC) if not refused(call(client_for(make_member("student")), *op))}
    assert open_routes == OPEN_WITHOUT_CONSENT


def test_public_routes_never_need_consent(consent_on):
    for method, path in [("GET", "/api/config"), ("GET", "/api/health"), ("GET", "/api/support/contact")]:
        assert Client().generic(method, path).status_code == 200, path


def test_me_tells_the_app_to_show_the_consent_screen(consent_on, make_member, client_for, settings):
    body = client_for(make_member("student")).get("/api/me").json()
    assert body["needs_consent"] is True and body["policy_version"] == settings.POLICY_VERSION
    assert (
        client_for(make_member("student")).get("/api/me/settings").status_code == 403
    )  # settings itself needs it, /api/me does not


def test_accepting_opens_everything(consent_on, make_member, client_for, settings):
    m = make_member("student")
    assert refused(client_for(m).get("/api/matches"))
    assert client_for(m).post("/api/me/consent", {"policy_version": settings.POLICY_VERSION}).status_code == 200
    assert client_for(m).get("/api/matches").status_code == 200
    assert client_for(m).get("/api/me").json()["needs_consent"] is False


def test_a_new_policy_version_locks_everyone_out_until_they_accept_it(consent_on, make_member, client_for, settings):
    m = make_member("student")
    accept(m, "2026-01")
    assert client_for(m).get("/api/matches").status_code == 200
    settings.POLICY_VERSION = "2026-07"  # the lawyer's new text goes live: a setting change, no code change
    assert refused(client_for(m).get("/api/matches")) and refused(client_for(m).get("/api/notifications"))
    me = client_for(m).get("/api/me").json()
    assert me["needs_consent"] is True and me["policy_version"] == "2026-07"
    assert (
        client_for(m).post("/api/me/consent", {"policy_version": "2026-01"}).status_code == 422
    )  # the old text no longer counts
    assert client_for(m).post("/api/me/consent", {"policy_version": "2026-07"}).status_code == 200
    assert client_for(m).get("/api/matches").status_code == 200
    assert list(Consent.objects.filter(member=m).order_by("id").values_list("policy_version", flat=True)) == [
        "2026-01",
        "2026-07",
    ]  # history kept


def test_only_the_current_version_counts_not_the_newest_timestamp(consent_on, make_member, client_for, settings):
    m = make_member("student")
    accept(m, "2025-01")
    accept(m, "2024-06", days_ago=-1)  # an old version with a later timestamp must not pass
    assert refused(client_for(m).get("/api/matches"))


def test_consent_is_per_member(consent_on, make_member, client_for):
    a, b = make_member("student"), make_member("student")
    accept(a)
    assert client_for(a).get("/api/matches").status_code == 200 and refused(client_for(b).get("/api/matches"))


def test_privacy_rights_work_without_consent_and_without_an_invite(consent_on, beta_on, make_member, client_for):
    m = make_member("student")
    c = client_for(m)
    assert c.get("/api/me").status_code == 200
    assert c.post("/api/support", {"kind": "grievance", "message": "I want to complain"}).status_code == 202
    assert c.post("/api/me/export").status_code == 202
    assert c.post("/api/me/deletion", {"confirm": "DELETE"}).status_code == 202


def test_consent_is_checked_before_the_beta_gate(consent_on, beta_on, make_member, client_for):
    """A brand-new sign-up accepts the terms first (Welcome screen), then meets the invite screen."""
    m = make_member("student")
    assert refused(client_for(m).get("/api/matches"))
    accept(m)
    assert client_for(m).get("/api/matches").json()["error"]["code"] == "beta_required"


def test_a_new_member_can_accept_before_they_have_an_invite(consent_on, beta_on, make_member, client_for, settings):
    m = make_member("student")
    assert client_for(m).post("/api/me/consent", {"policy_version": settings.POLICY_VERSION}).status_code == 200


def test_the_error_uses_the_standard_format(consent_on, make_member, client_for):
    r = client_for(make_member("student")).get("/api/matches")
    assert r.status_code == 403
    assert set(r.json()["error"]) == {"code", "message", "details"} and r.json()["error"]["code"] == "consent_required"


def test_suspended_and_deleted_members_hit_their_own_error_first(consent_on, make_member, client_for):
    assert (
        client_for(make_member("student", suspended_at=timezone.now())).get("/api/matches").json()["error"]["code"]
        == "account_suspended"
    )
    assert (
        client_for(make_member("student", deleted_at=timezone.now())).get("/api/matches").json()["error"]["code"]
        == "account_deleted"
    )
