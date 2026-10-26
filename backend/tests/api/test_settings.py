"""Stage 6: the Settings screen endpoints (profile summary, privacy, appearance, notification preferences) and consent."""

import json

import pytest

from apps.accounts.models import Consent, Member
from apps.events.models import Event

pytestmark = pytest.mark.django_db


def patch(client, path, body):
    return client.patch(path, json.dumps(body), content_type="application/json")


# -- GET /api/me/settings --------------------------------------------------------------------------
def test_settings_returns_the_whole_screen_in_one_call(make_member, client_for, settings):
    m = make_member("founder", display_name="Asha Rao", city="Chennai")
    r = client_for(m, email="asha.rao@example.org").get("/api/me/settings")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"profile", "privacy", "appearance", "notifications", "blocked_count", "export", "consent", "support"}
    assert body["profile"]["email_hint"] == "a***@example.org"  # a hint, never the address
    assert "asha.rao" not in r.content.decode()
    assert body["appearance"] == {"theme": "system", "accent": "emerald", "swipe_tabs": True}
    assert body["notifications"]["intros"] == {"in_app": True, "email": True}
    assert body["notifications"]["messages"] == {"in_app": True, "email": False}
    assert body["blocked_count"] == 0 and body["export"] is None
    assert body["consent"]["policy_version"] == settings.POLICY_VERSION
    assert body["support"]["support_email"] == settings.SUPPORT_EMAIL
    assert set(body["support"]["grievance"]) == {"name", "email", "address"}


def test_settings_needs_a_token(client_for):
    assert client_for().get("/api/me/settings").status_code == 401


def test_settings_are_always_my_own(make_member, client_for):
    a, b = make_member("student", display_name="Alice"), make_member("student", display_name="Bob", city="Pune")
    patch(client_for(b), "/api/me/appearance", {"accent": "rose"})
    seen_by_a = client_for(a).get("/api/me/settings").json()
    assert seen_by_a["profile"]["display_name"] == "Alice" and seen_by_a["appearance"]["accent"] == "emerald"


# -- privacy ---------------------------------------------------------------------------------------
def test_privacy_can_be_changed_and_is_saved(make_member, client_for):
    m = make_member("founder", level=2)
    r = patch(client_for(m), "/api/me/privacy", {"profile_visibility": "hidden", "visible_to_org": True, "circuits_opt_in": True})
    assert r.status_code == 200 and r.json()["profile_visibility"] == "hidden" and r.json()["circuits_opt_in"] is True
    m.refresh_from_db()
    assert (m.profile_visibility, m.visible_to_org, m.circuits_opt_in) == ("hidden", True, True)
    assert Event.objects.filter(
        actor=m, type="member.privacy_updated", payload__fields=["circuits_opt_in", "profile_visibility", "visible_to_org"]
    ).exists()


def test_privacy_rejects_unknown_values_and_fields(make_member, client_for):
    c = client_for(make_member())
    assert patch(c, "/api/me/privacy", {"profile_visibility": "everyone"}).status_code == 422
    assert patch(c, "/api/me/privacy", {"is_minor": False}).status_code == 422  # not a privacy setting: never writable here
    assert patch(c, "/api/me/privacy", {"visible_to_org": None}).status_code == 422


@pytest.mark.parametrize(
    "body", [{"profile_visibility": "public"}, {"allow_requests": True}, {"profile_visibility": "public", "allow_requests": True}]
)
def test_a_minor_cannot_go_public_or_open_requests_to_strangers_whatever_the_client_sends(make_member, client_for, body):
    m = make_member("student", is_minor=True)
    assert (m.profile_visibility, m.allow_requests) == ("hidden", False)  # the defaults for under-18s
    r = patch(client_for(m), "/api/me/privacy", body)
    assert r.status_code == 403 and r.json()["error"]["code"] == "under_18_restricted"
    m.refresh_from_db()
    assert (m.profile_visibility, m.allow_requests) == ("hidden", False)


def test_a_minor_may_still_tighten_or_loosen_inside_the_safe_range(make_member, client_for):
    m = make_member("student", is_minor=True)
    r = patch(
        client_for(m), "/api/me/privacy", {"profile_visibility": "members", "visible_to_org": True, "allow_requests": False}
    )
    assert r.status_code == 200 and r.json()["profile_visibility"] == "members"


def test_circuits_opt_in_still_needs_level_2(make_member, client_for):
    assert patch(client_for(make_member("founder", level=1)), "/api/me/privacy", {"circuits_opt_in": True}).status_code == 403


def test_allow_requests_off_stops_strangers_but_not_connections_or_org_mates(make_member, make_org, connect, client_for):
    org = make_org()
    target = make_member("founder", allow_requests=False)
    stranger, friend = make_member("mentor"), make_member("mentor")
    mate = make_member("student", org=org)
    target.organisation = org
    target.save()
    connect(target, friend)
    assert client_for(stranger).post("/api/conversations", {"member_id": target.pk, "body": "hi"}).status_code == 404
    assert client_for(stranger).post("/api/connections/requests", {"member_id": target.pk, "note": ""}).status_code == 404
    assert client_for(friend).post("/api/conversations", {"member_id": target.pk, "body": "hi"}).status_code == 201
    assert client_for(mate).post("/api/connections/requests", {"member_id": target.pk, "note": ""}).status_code == 201
    target.allow_requests = True
    target.save()
    assert client_for(stranger).post("/api/conversations", {"member_id": target.pk, "body": "hi"}).status_code == 201


def test_me_carries_allow_requests_appearance_and_consent_state(make_member, client_for):
    body = client_for(make_member()).get("/api/me").json()
    assert body["allow_requests"] is True and body["appearance"]["accent"] == "emerald"
    assert body["needs_consent"] is False and body["policy_version"] == "2026-01"


# -- appearance ------------------------------------------------------------------------------------
@pytest.mark.parametrize("accent", ["emerald", "sky", "indigo", "rose", "lime", "mono"])
@pytest.mark.parametrize("theme", ["system", "dark", "light"])
def test_every_allowed_theme_and_accent_is_accepted(make_member, client_for, theme, accent):
    m = make_member()
    r = patch(client_for(m), "/api/me/appearance", {"theme": theme, "accent": accent, "swipe_tabs": False})
    assert r.status_code == 200 and r.json() == {"theme": theme, "accent": accent, "swipe_tabs": False}
    m.refresh_from_db()
    assert m.appearance == {"theme": theme, "accent": accent, "swipe_tabs": False}


@pytest.mark.parametrize(
    "body",
    [
        {"theme": "solarized"},
        {"theme": "DARK"},
        {"accent": "orange"},  # warm accents are banned (DESIGN.md §12)
        {"accent": "#ff0000"},  # no free colour picker
        {"accent": None},
        {"swipe_tabs": "yes"},
        {"swipe_tabs": 1},
        {"font_size": 20},
    ],
)
def test_invalid_appearance_values_are_rejected_and_nothing_is_saved(make_member, client_for, body):
    m = make_member()
    r = patch(client_for(m), "/api/me/appearance", {"accent": "sky", **body} if "accent" not in body else body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    m.refresh_from_db()
    assert m.appearance == {}


def test_appearance_is_a_partial_update_and_defaults_fill_the_rest(make_member, client_for):
    m = make_member()
    assert patch(client_for(m), "/api/me/appearance", {"accent": "lime"}).json() == {
        "theme": "system",
        "accent": "lime",
        "swipe_tabs": True,
    }
    assert patch(client_for(m), "/api/me/appearance", {"theme": "dark"}).json() == {
        "theme": "dark",
        "accent": "lime",
        "swipe_tabs": True,
    }
    assert client_for(m).get("/api/me").json()["appearance"] == {"theme": "dark", "accent": "lime", "swipe_tabs": True}


def test_a_garbage_stored_appearance_never_reaches_the_client(make_member, client_for):
    m = make_member(appearance={"theme": "neon", "accent": "orange", "swipe_tabs": "maybe"})
    assert client_for(m).get("/api/me").json()["appearance"] == {"theme": "system", "accent": "emerald", "swipe_tabs": True}


def test_appearance_cannot_be_written_for_someone_else(make_member, client_for):
    a, b = make_member(), make_member()
    patch(client_for(a), "/api/me/appearance", {"accent": "rose"})
    b.refresh_from_db()
    assert b.appearance == {}  # there is no id in the URL to tamper with: it is always "me"


# -- notification preferences ----------------------------------------------------------------------
def test_notification_preferences_default_and_change_one_channel(make_member, client_for):
    m = make_member()
    r = patch(client_for(m), "/api/me/notification-preferences", {"intros": {"email": False}, "messages": {"email": True}})
    assert r.status_code == 200
    body = r.json()
    assert body["intros"] == {"in_app": True, "email": False}
    assert body["messages"] == {"in_app": True, "email": True}
    assert body["circuits"] == {"in_app": True, "email": True}  # untouched
    m.refresh_from_db()
    assert m.notification_prefs["intros"]["email"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"newsletter": {"email": True}},
        {"intros": {"sms": True}},
        {"intros": {"email": "yes"}},
        {"intros": True},
        {"intros": None},
        {"intros": {"email": None}},
    ],
)
def test_bad_notification_preferences_are_rejected(make_member, client_for, body):
    m = make_member()
    assert patch(client_for(m), "/api/me/notification-preferences", body).status_code == 422
    m.refresh_from_db()
    assert m.notification_prefs == {}


# -- consent ---------------------------------------------------------------------------------------
def test_accepting_the_current_policy_is_recorded_once(make_member, client_for, settings):
    m = make_member()
    c = client_for(m)
    first = c.post("/api/me/consent", {"policy_version": settings.POLICY_VERSION})
    again = c.post("/api/me/consent", {"policy_version": settings.POLICY_VERSION})
    assert first.status_code == again.status_code == 200
    assert first.json() == again.json()
    assert Consent.objects.filter(member=m, policy_version=settings.POLICY_VERSION).count() == 1
    assert Event.objects.filter(actor=m, type="consent.accepted").count() == 1


def test_accepting_an_old_or_invented_version_is_refused(make_member, client_for):
    m = make_member()
    r = client_for(m).post("/api/me/consent", {"policy_version": "2020-01"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "policy_version_mismatch"
    assert not Consent.objects.filter(member=m).exists()


def test_consent_is_always_for_me(make_member, client_for, settings):
    a, b = make_member(), make_member()
    client_for(a).post("/api/me/consent", {"policy_version": settings.POLICY_VERSION})
    assert Consent.objects.filter(member=b).count() == 0 and Consent.objects.filter(member=a).count() == 1


def test_profile_patch_still_works_and_rejects_privacy_fields(make_member, client_for):
    m = make_member()
    assert patch(client_for(m), "/api/me", {"city": "Madurai"}).json()["city"] == "Madurai"
    assert patch(client_for(m), "/api/me", {"allow_requests": True}).status_code == 422
    assert Member.objects.get(pk=m.pk).city == "Madurai"
