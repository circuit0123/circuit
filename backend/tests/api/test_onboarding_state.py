"""Resumable onboarding: GET/PATCH /api/onboarding/state (F1). Saved per step on the member; src is first-touch."""

import json
import logging

import pytest
from django.utils import timezone

from apps.accounts import deletion, export
from apps.accounts.models import Member
from apps.events.models import Event

pytestmark = pytest.mark.django_db
URL = "/api/onboarding/state"
DEFAULT = [
    "invite",
    "name",
    "role",
    "age",
    "safety",
    "where",
    "work",
    "offers",
    "needs",
    "organisation",
    "photo",
    "colour",
    "ready",
]


def patch(client, **body):
    return client.patch(URL, json.dumps(body))


# -- reading -------------------------------------------------------------------------------------------------
def test_a_new_member_starts_at_the_beginning(make_member, client_for):
    r = client_for(make_member("student")).get(URL)
    assert r.status_code == 200
    body = r.json()
    assert body["branch"] == "default" and body["steps"] == DEFAULT
    assert body["current_step"] is None and body["completed_at"] is None and body["answers"] == {} and body["signup_source"] == ""
    assert "invite" in body["skip"] and "safety" in body["skip"]  # no beta, an adult: neither screen is needed


def test_what_we_already_know_is_skipped(make_member, make_org, client_for):
    org = make_org()
    m = make_member("student", org=org, display_name="Asha Rao", city="Chennai")
    skip = client_for(m).get(URL).json()["skip"]
    assert {"name", "where", "organisation"} <= set(skip)


def test_the_safety_screen_is_for_under_18s_only(make_member, client_for):
    kid = make_member("student", is_minor=True)
    assert "safety" not in client_for(kid).get(URL).json()["skip"]


def test_the_invite_screen_shows_only_while_the_beta_is_on_and_there_is_no_access(make_member, client_for, beta_on, let_in):
    m = make_member("student")
    assert "invite" not in client_for(m).get(URL).json()["skip"]
    let_in(m)
    assert "invite" in client_for(m).get(URL).json()["skip"]


def test_the_role_answer_picks_the_branch(make_member, client_for):
    c = client_for(make_member("student"))
    patch(c, answers={"role": {"choice": "invest"}})
    r = c.get(URL).json()
    assert r["branch"] == "investor" and "focus" in r["steps"] and "offers" not in r["steps"]
    patch(c, answers={"role": {"choice": "partner"}})
    r = c.get(URL).json()
    assert r["branch"] == "partner" and "org_verify" in r["steps"] and "needs" not in r["steps"]
    patch(c, answers={"role": {"choice": "find_work"}})
    assert c.get(URL).json()["branch"] == "default"


def test_an_investor_member_is_on_the_investor_branch(make_member, client_for):
    assert client_for(make_member("investor")).get(URL).json()["branch"] == "investor"


# -- saving --------------------------------------------------------------------------------------------------
def test_answers_are_saved_per_step_and_merged(make_member, client_for):
    c = client_for(make_member("student"))
    r = patch(c, current_step="role", answers={"name": {"first": "Asha", "last": "Rao"}})
    assert r.status_code == 200 and r.json()["current_step"] == "role"
    patch(c, current_step="age", answers={"role": {"choice": "find_work"}})
    patch(c, answers={"name": {"first": "Asha", "last": "R"}})  # an edit replaces that step only
    body = c.get(URL).json()
    assert body["current_step"] == "age"
    assert body["answers"] == {"name": {"first": "Asha", "last": "R"}, "role": {"choice": "find_work"}}


def test_resuming_returns_exactly_where_they_stopped(make_member, client_for):
    m = make_member("student")
    patch(client_for(m), current_step="offers", answers={"work": {"bio": "I build apps"}})
    again = client_for(m).get(URL).json()  # a new session
    assert again["current_step"] == "offers" and again["answers"]["work"] == {"bio": "I build apps"}


def test_completing_sets_the_time_once(make_member, client_for):
    c = client_for(make_member("student"))
    first = patch(c, completed=True).json()["completed_at"]
    assert first
    assert patch(c, completed=True).json()["completed_at"] == first


def test_signup_source_sticks_to_the_first_touch(make_member, client_for):
    m = make_member("student")
    c = client_for(m)
    assert patch(c, signup_source="landing-students").json()["signup_source"] == "landing-students"
    assert patch(c, signup_source="invite").json()["signup_source"] == "landing-students"
    assert Member.objects.get(pk=m.pk).signup_source == "landing-students"


@pytest.mark.parametrize("src", ["Landing Students!", "landing students", "x" * 41, "a/b", "<script>"])
def test_a_bad_source_is_a_422(make_member, client_for, src):
    m = make_member("student")
    assert patch(client_for(m), signup_source=src).status_code == 422
    assert Member.objects.get(pk=m.pk).signup_source == ""


@pytest.mark.parametrize(
    "body",
    [
        {"current_step": "not-a-step"},
        {"answers": {"not-a-step": {"a": 1}}},
        {"answers": {"name": "a string, not an object"}},
        {"completed": "yes"},
        {"completed": 1},
        {"role": "founder"},  # unknown field: never silently ignored
        {"is_minor": True},
    ],
)
def test_unknown_steps_fields_and_loose_types_are_422(make_member, client_for, body):
    assert patch(client_for(make_member("student")), **body).status_code == 422


def test_a_huge_answer_is_refused_and_nothing_is_saved(make_member, client_for):
    m = make_member("student")
    r = patch(client_for(m), answers={"work": {"bio": "x" * 5000}, "name": {"first": "A"}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "answer_too_large"
    assert Member.objects.get(pk=m.pk).onboarding == {}


def test_this_endpoint_cannot_change_the_role_or_any_other_profile_field(make_member, client_for):
    m = make_member("student")
    patch(client_for(m), answers={"role": {"choice": "invest"}}, current_step="role")
    fresh = Member.objects.get(pk=m.pk)
    assert fresh.role == "student" and not fresh.is_minor  # the answer is only a saved choice; PATCH /api/me changes the role


# -- who can read what -------------------------------------------------------------------------------------------
def test_each_member_has_their_own_state_and_there_is_no_id_to_tamper_with(make_member, client_for):
    a, b = make_member("student"), make_member("student")
    patch(client_for(a), current_step="needs", answers={"work": {"bio": "secret plans"}}, signup_source="landing-students")
    other = client_for(b).get(URL).json()
    assert other["current_step"] is None and other["answers"] == {} and other["signup_source"] == ""
    assert client_for(b).get(f"{URL}/{a.pk}").status_code == 404


def test_anonymous_callers_are_refused(client_for):
    assert client_for().get(URL).status_code == 401
    assert client_for().patch(URL, "{}").status_code == 401


def test_it_stays_open_while_the_beta_gate_is_on_but_the_consent_gate_still_applies(make_member, client_for, beta_on, consent_on):
    m = make_member("student")
    r = client_for(m).get(URL)
    assert r.status_code == 403 and r.json()["error"]["code"] == "consent_required"
    from apps.accounts.models import Consent

    Consent.objects.create(member=m, policy_version="2026-01", accepted_at=timezone.now())
    assert client_for(m).get(URL).status_code == 200  # no invite, beta on: still open (the invite screen is a step)
    assert client_for(m).get("/api/matches").json()["error"]["code"] == "beta_required"


def test_saving_is_rate_limited(make_member, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "onboarding_state": (2, 3600)}
    c = client_for(make_member("student"))
    assert patch(c, current_step="name").status_code == 200 and patch(c, current_step="role").status_code == 200
    r = patch(c, current_step="age")
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
    assert c.get(URL).status_code == 200  # reading is not limited


# -- privacy ---------------------------------------------------------------------------------------------------------
def test_the_event_records_the_step_but_never_the_answers(make_member, client_for):
    m = make_member("student")
    patch(client_for(m), current_step="work", answers={"work": {"bio": "my private story"}})
    ev = Event.objects.get(type="onboarding.updated")
    assert ev.payload == {"step": "work", "completed": False} and "private" not in json.dumps(ev.payload)


def test_answers_never_reach_the_logs(make_member, client_for, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    patch(client_for(make_member("student")), answers={"work": {"bio": "my very private story"}})
    seen = capsys.readouterr().out + caplog.text
    assert "my very private story" not in seen


def test_the_export_includes_the_saved_state(make_member, client_for):
    m = make_member("student")
    patch(client_for(m), current_step="needs", answers={"work": {"bio": "hello"}}, signup_source="landing-founders")
    profile = export.member_data(Member.objects.get(pk=m.pk))["profile"]
    assert profile["signup_source"] == "landing-founders" and profile["onboarding"]["answers"]["work"] == {"bio": "hello"}


def test_deleting_the_account_clears_the_answers_but_keeps_the_landing_page_label(make_member, client_for):
    m = make_member("student")
    patch(client_for(m), current_step="needs", answers={"work": {"bio": "hello"}}, signup_source="landing-founders")
    deletion.request_deletion(m)
    deletion.erase(m)
    fresh = Member.objects.get(pk=m.pk)
    assert fresh.onboarding == {} and fresh.signup_source == "landing-founders"
