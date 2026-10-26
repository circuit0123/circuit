"""B7 part 1: accent rename, the age answer sets is_minor, MeOut additions, read receipts setting, llm_available."""

import json

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.accounts.models import Member
from apps.events.models import Event
from apps.matching.models import Capability, Need, Offer
from apps.moderation.models import AuditLog

pytestmark = pytest.mark.django_db


def patch(client, path, body):
    return client.patch(path, json.dumps(body), content_type="application/json")


# -- accent: emerald out, mint in --------------------------------------------------------------------------------
def test_the_default_accent_is_emerald(make_member, client_for):
    assert client_for(make_member()).get("/api/me").json()["appearance"]["accent"] == "emerald"


def test_the_old_name_mint_is_accepted_and_stored_as_emerald(make_member, client_for):
    m = make_member()
    r = patch(client_for(m), "/api/me/appearance", {"accent": "mint"})
    assert r.status_code == 200 and r.json()["accent"] == "emerald"
    m.refresh_from_db()
    assert m.appearance["accent"] == "emerald"


def test_a_stored_mint_is_read_as_emerald(make_member, client_for):
    m = make_member()
    Member.objects.filter(pk=m.pk).update(appearance={"accent": "mint", "theme": "dark"})
    assert client_for(m).get("/api/me").json()["appearance"] == {"theme": "dark", "accent": "emerald", "swipe_tabs": True}


def test_an_unknown_accent_is_still_a_422(make_member, client_for):
    assert patch(client_for(make_member()), "/api/me/appearance", {"accent": "purple"}).status_code == 422


def test_the_migration_rewrites_mint_rows():
    from importlib import import_module

    mod = import_module("apps.accounts.migrations.0009_accent_emerald")
    m = Member.objects.create(
        auth_user_id="00000000-0000-0000-0000-0000000000aa", display_name="Old", appearance={"accent": "mint"}
    )
    mod.mint_to_emerald(MigrationExecutor(connection).loader.project_state(("accounts", "0009_accent_emerald")).apps, None)
    m.refresh_from_db()
    assert m.appearance["accent"] == "emerald"


# -- the age answer ------------------------------------------------------------------------------------------------
def save_age(client, adult):
    return client.patch("/api/onboarding/state", json.dumps({"answers": {"age": {"adult": adult}}}))


def test_answering_under_18_applies_every_under_18_rule(make_member, client_for):
    m = make_member("student", circuits_opt_in=True, profile_visibility="public", allow_requests=True)
    r = save_age(client_for(m), False)
    assert r.status_code == 200 and "safety" not in r.json()["skip"]
    m.refresh_from_db()
    assert m.is_minor and m.profile_visibility == "hidden" and not m.allow_requests and not m.circuits_opt_in
    assert Event.objects.filter(type="member.marked_minor", actor=m).count() == 1
    assert client_for(m).get("/api/me").json()["is_minor"] is True


def test_under_18_forces_the_student_role(make_member, client_for):
    m = make_member("founder")
    save_age(client_for(m), False)
    m.refresh_from_db()
    assert m.role == "student"


def test_answering_adult_does_not_set_it(make_member, client_for):
    m = make_member("student")
    save_age(client_for(m), True)
    m.refresh_from_db()
    assert not m.is_minor and not Event.objects.filter(type="member.marked_minor").exists()


def test_a_minor_cannot_clear_the_flag_by_answering_again(make_member, client_for):
    m = make_member("student")
    c = client_for(m)
    save_age(c, False)
    save_age(c, True)
    m.refresh_from_db()
    assert m.is_minor
    assert patch(c, "/api/me/privacy", {"profile_visibility": "public"}).status_code == 403  # the under-18 rules now apply


def test_marking_a_minor_twice_records_one_event(make_member, client_for):
    m = make_member("student")
    save_age(client_for(m), False)
    save_age(client_for(m), False)
    assert Event.objects.filter(type="member.marked_minor").count() == 1


def test_only_a_super_admin_can_confirm_an_adult(make_member, staff_request):
    from django.contrib import admin

    from apps.accounts.admin import MemberAdmin

    m = make_member("student", is_minor=True)
    request, _ = staff_request
    MemberAdmin(Member, admin.site).confirm_adult(request, Member.objects.filter(pk=m.pk))
    m.refresh_from_db()
    assert not m.is_minor and AuditLog.objects.filter(action="confirm_adult", target_id=str(m.pk)).exists()


# -- MeOut additions ----------------------------------------------------------------------------------------------
def test_me_says_which_startup_a_founder_is_on(make_member, make_startup, client_for):
    founder = make_member("founder")
    startup = make_startup(claimed_by=founder)
    body = client_for(founder).get("/api/me").json()
    assert body["startup_id"] == startup.pk
    assert client_for(make_member("student")).get("/api/me").json()["startup_id"] is None


def test_me_says_whether_needs_and_offers_are_set(make_member, lists, client_for):
    m = make_member("student")
    assert client_for(m).get("/api/me").json()["has_needs_and_offers"] is False
    cap = Capability.objects.first()
    Need.objects.create(member=m, capability=cap)
    assert client_for(m).get("/api/me").json()["has_needs_and_offers"] is False  # both are needed for a circuit
    Offer.objects.create(member=m, capability=Capability.objects.exclude(pk=cap.pk).first())
    assert client_for(m).get("/api/me").json()["has_needs_and_offers"] is True


# -- read receipts setting ------------------------------------------------------------------------------------------
def test_read_receipts_are_off_by_default_and_can_be_switched_on(make_member, client_for):
    m = make_member()
    c = client_for(m)
    assert c.get("/api/me/settings").json()["privacy"]["read_receipts"] is False
    r = patch(c, "/api/me/privacy", {"read_receipts": True})
    assert r.status_code == 200 and r.json()["read_receipts"] is True
    assert c.get("/api/me").json()["read_receipts"] is True


def test_read_receipts_must_be_a_real_boolean(make_member, client_for):
    assert patch(client_for(make_member()), "/api/me/privacy", {"read_receipts": "yes"}).status_code == 422


# -- config ---------------------------------------------------------------------------------------------------------
def test_config_says_whether_the_ai_is_available(client, settings):
    settings.LLM_PROVIDER = "fake"
    settings.LLM_DAILY_CALL_LIMIT = 0
    assert client.get("/api/config").json()["llm_available"] is True
    settings.LLM_PROVIDER = "none"
    assert client.get("/api/config").json()["llm_available"] is False


def test_config_says_no_ai_once_the_daily_cap_is_used_up(client, settings):
    from core import usage

    settings.LLM_PROVIDER = "fake"
    settings.LLM_DAILY_CALL_LIMIT = 2
    usage.bump("llm_calls", by=2)
    assert client.get("/api/config").json()["llm_available"] is False
