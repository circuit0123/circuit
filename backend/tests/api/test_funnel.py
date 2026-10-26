"""The sign-up funnel per source: counts, hiding of small counts, no personal data, the click counter and the admin page."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.beta.funnel import funnel, render
from apps.beta.models import BetaAccess, JoinVisit
from apps.events.services import record

pytestmark = pytest.mark.django_db


def _row(src):
    return next((r for r in funnel() if r["src"] == src), None)


def _people(make_member, n, src, *, beta=False, done=False, acted=False, **kw):
    out = []
    for _ in range(n):
        m = make_member(signup_source=src, **kw)
        if beta:
            BetaAccess.objects.create(member=m, source="code")
        if done:
            m.onboarding = {"completed_at": "2026-03-01T10:00:00+05:30"}
            m.save()
        if acted:
            record("intro.requested", actor=m, target_type="intro", target_id=1)
        out.append(m)
    return out


def test_each_step_counts_members_from_that_source(make_member):
    _people(make_member, 6, "landing-students", beta=True, done=True, acted=True)
    _people(make_member, 3, "landing-students", beta=True)  # got in but never finished
    _people(make_member, 7, "landing-founders")  # signed up, no beta access
    JoinVisit.objects.create(src="landing-students", day=timezone.localdate(), count=40)
    row = _row("landing-students")
    assert [row[s]["value"] for s in ("clicks", "signed_up", "beta_access", "onboarding_done", "first_match_action")] == [
        40,
        9,
        9,
        6,
        6,
    ]
    founders = _row("landing-founders")
    assert founders["signed_up"]["value"] == 7 and founders["beta_access"]["hidden"]


def test_counts_under_five_are_hidden_not_zeroed(make_member):
    _people(make_member, 5, "a", beta=True)
    _people(make_member, 4, "b", beta=True)
    assert _row("a")["signed_up"] == {"value": 5, "hidden": False}
    assert _row("b")["signed_up"] == {"value": None, "hidden": True}
    assert "<5" in render(funnel())


def test_revoked_simulated_and_deleted_members_are_left_out(make_member):
    group = _people(make_member, 8, "x", beta=True)
    BetaAccess.objects.filter(member=group[0]).update(revoked_at=timezone.now())
    _people(make_member, 9, "x", is_simulated=True)
    _people(make_member, 9, "x", deleted_at=timezone.now())
    row = _row("x")
    assert row["signed_up"]["value"] == 8 and row["beta_access"]["value"] == 7


def test_a_member_with_no_source_is_listed_as_none(make_member):
    _people(make_member, 5, "")
    assert _row("(none)")["signed_up"]["value"] == 5


def test_days_window(make_member):
    old = _people(make_member, 6, "w")
    type(old[0]).objects.filter(pk__in=[m.pk for m in old]).update(created_at=timezone.now() - timedelta(days=40))
    _people(make_member, 5, "w")
    assert _row("w")["signed_up"]["value"] == 11
    assert [r for r in funnel(days=30) if r["src"] == "w"][0]["signed_up"]["value"] == 5


def test_nothing_that_identifies_a_person_is_in_the_output(make_member):
    for m in _people(
        make_member, 6, "p", beta=True, done=True, acted=True, display_name="Zainab Qureshi", email="zainab@example.org"
    ):
        m.save()
    text = render(funnel()) + str(funnel())
    assert "Zainab" not in text and "example.org" not in text


def test_command_prints_the_table(make_member, capsys):
    _people(make_member, 5, "cmd")
    call_command("funnel", "--days", "30")
    out = capsys.readouterr().out
    assert "source" in out and "cmd" in out


def test_visit_counts_per_source_and_day(client_for):
    c = client_for()
    for _ in range(3):
        assert c.post("/api/join/visit", {"src": "landing-students"}).status_code == 204
    assert c.post("/api/join/visit", {"src": ""}).status_code == 204
    assert JoinVisit.objects.get(src="landing-students").count == 3
    assert JoinVisit.objects.get(src="").count == 1


def test_visit_refuses_a_bad_source_and_stores_nothing_else(client_for):
    c = client_for()
    assert c.post("/api/join/visit", {"src": "Bad Source!"}).status_code == 422
    assert c.post("/api/join/visit", {"src": "x" * 41}).status_code == 422
    assert not JoinVisit.objects.exists()
    assert {f.name for f in JoinVisit._meta.get_fields()} == {"id", "src", "day", "count"}


def test_visit_is_rate_limited_per_address(client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "join_visit": (2, 3600)}
    c = client_for()
    assert [c.post("/api/join/visit", {"src": "s"}).status_code for _ in range(3)] == [204, 204, 429]


def _staff(verified=True):
    user = get_user_model().objects.create_superuser("asha", password="a-long-enough-pass-1")
    client = Client()
    client.force_login(user)
    if verified:
        device = TOTPDevice.objects.create(user=user, name="d", confirmed=True)
        session = client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()
    return client


def test_admin_metrics_page_shows_the_funnel_to_a_verified_superuser(make_member, settings):
    _people(make_member, 6, "landing-students", beta=True)
    r = _staff().get(f"/{settings.ADMIN_PATH}metrics/")
    assert r.status_code == 200 and b"landing-students" in r.content and b"Sign-up funnel" in r.content


def test_admin_metrics_page_needs_login_and_2fa(settings):
    assert Client().get(f"/{settings.ADMIN_PATH}metrics/").status_code == 302
    r = _staff(verified=False).get(f"/{settings.ADMIN_PATH}metrics/")
    assert r.status_code == 302 and b"Sign-up funnel" not in r.content
