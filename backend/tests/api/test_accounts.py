import json

import pytest

from apps.accounts.models import WorkEmailVerification
from apps.events.models import Event
from apps.matching.models import Need, Offer
from apps.moderation.models import Block
from core import codes
from core.llm import FakeLLM

pytestmark = pytest.mark.django_db


def events(type_):
    return Event.objects.filter(type=type_)


# -- profile ------------------------------------------------------------------
def test_me_returns_own_profile(make_member, client_for):
    m = make_member("student", city="Chennai")
    body = client_for(m).get("/api/me").json()
    assert body["id"] == m.pk and body["city"] == "Chennai" and body["lat"] is None


def test_patch_me_updates_fields_and_location_and_logs_event(make_member, client_for):
    m = make_member("student")
    r = client_for(m).patch("/api/me", json.dumps({"bio": "Hello there", "lat": 13.1, "lng": 80.2}))
    assert r.status_code == 200 and r.json()["bio"] == "Hello there" and round(r.json()["lat"], 1) == 13.1
    assert events("member.profile_updated").filter(actor=m).exists()


def test_patch_me_needs_both_lat_and_lng(make_member, client_for):
    r = client_for(make_member()).patch("/api/me", json.dumps({"lat": 13.1}))
    assert r.status_code == 422


def test_role_can_change_between_self_serve_roles_and_is_logged(make_member, client_for):
    m = make_member("student")
    r = client_for(m).patch("/api/me", json.dumps({"role": "founder"}))
    assert r.status_code == 200 and r.json()["role"] == "founder"
    assert events("member.role_changed").filter(actor=m, payload__new="founder").exists()


def test_role_cannot_become_admin(make_member, client_for):
    m = make_member("student")
    r = client_for(m).patch("/api/me", json.dumps({"role": "super_admin"}))
    assert r.status_code == 422  # not even a valid choice
    m.refresh_from_db()
    assert m.role == "student"


def test_admins_cannot_switch_themselves_to_a_normal_role(make_member, make_org, client_for):
    m = make_member("partner_admin", org=make_org())
    assert client_for(m).patch("/api/me", json.dumps({"role": "student"})).status_code == 403


def test_minor_cannot_become_founder_or_public(make_member, client_for):
    m = make_member("student", is_minor=True)
    assert client_for(m).patch("/api/me", json.dumps({"role": "founder"})).status_code == 403
    r = client_for(m).patch("/api/me/privacy", json.dumps({"profile_visibility": "public"}))
    assert r.status_code == 403 and r.json()["error"]["code"] == "under_18_restricted"
    m.refresh_from_db()
    assert m.profile_visibility == "hidden"


def test_circuit_opt_in_needs_level_2(make_member, client_for):
    low, ok = make_member("founder", level=1), make_member("founder", level=2)
    assert client_for(low).patch("/api/me/privacy", json.dumps({"circuits_opt_in": True})).status_code == 403
    assert client_for(ok).patch("/api/me/privacy", json.dumps({"circuits_opt_in": True})).json()["circuits_opt_in"] is True


def test_patch_me_rejects_unknown_choice(make_member, client_for):
    assert client_for(make_member()).patch("/api/me/privacy", json.dumps({"profile_visibility": "everyone"})).status_code == 422


def test_patch_me_no_longer_takes_privacy_fields_and_says_so(make_member, client_for):
    m = make_member()
    r = client_for(m).patch("/api/me", json.dumps({"profile_visibility": "public"}))
    assert r.status_code == 422  # not silently ignored: privacy has its own endpoint
    m.refresh_from_db()
    assert m.profile_visibility == "members"


# -- needs, offers, skills, traits -----------------------------------------------------
def test_set_needs_replaces_and_is_idempotent(lists, make_member, client_for):
    m = make_member()
    c = client_for(m)
    body = json.dumps([{"capability": "seo", "description": "need help"}, {"capability": "fundraising"}])
    assert c.put("/api/me/needs", body).status_code == 200
    assert c.put("/api/me/needs", body).status_code == 200
    assert Need.objects.filter(member=m).count() == 2
    r = c.put("/api/me/needs", json.dumps([{"capability": "seo", "description": "need help"}]))
    assert [x["capability"] for x in r.json()] == ["seo"] and Need.objects.filter(member=m).count() == 1
    assert c.get("/api/me/needs").json() == r.json()
    assert events("member.needs_set").filter(actor=m).count() == 3


def test_unchanged_need_keeps_embedding_changed_clears_it(lists, make_member, client_for):
    m = make_member()
    c = client_for(m)
    c.put("/api/me/offers", json.dumps([{"capability": "seo", "description": "a"}]))
    Offer.objects.filter(member=m).update(embedding=[0.1] * 384)
    c.put("/api/me/offers", json.dumps([{"capability": "seo", "description": "a"}]))
    assert Offer.objects.get(member=m).embedding is not None
    c.put("/api/me/offers", json.dumps([{"capability": "seo", "description": "b"}]))
    assert Offer.objects.get(member=m).embedding is None


def test_unknown_capability_is_422_and_changes_nothing(lists, make_member, client_for):
    m = make_member()
    client_for(m).put("/api/me/offers", json.dumps([{"capability": "seo"}]))
    r = client_for(m).put("/api/me/offers", json.dumps([{"capability": "seo"}, {"capability": "made-up"}]))
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_capability"
    assert Offer.objects.filter(member=m).count() == 1


def test_too_many_needs(lists, make_member, client_for):
    from apps.matching.models import Capability

    slugs = list(Capability.objects.values_list("slug", flat=True)[:9])
    r = client_for(make_member()).put("/api/me/needs", json.dumps([{"capability": s} for s in slugs]))
    assert r.status_code == 422 and r.json()["error"]["code"] == "too_many"


def test_set_skills_and_traits(lists, make_member, client_for):
    m = make_member()
    c = client_for(m)
    r = c.put("/api/me/skills", json.dumps([{"capability": "frontend-dev", "level": 3, "proof_url": "https://github.com/x/y"}]))
    assert r.json() == [{"capability": "frontend-dev", "level": 3, "proof_url": "https://github.com/x/y"}]
    assert c.put("/api/me/skills", json.dumps([{"capability": "seo", "level": 4}])).status_code == 422
    assert c.put("/api/me/traits", json.dumps(["deep-tech", "deep-tech"])).json() == ["deep-tech"]
    assert c.put("/api/me/traits", json.dumps(["nope"])).status_code == 422
    assert c.get("/api/me/traits").json() == ["deep-tech"]


def test_lists_are_public_to_signed_in_members(lists, make_member, client_for):
    c = client_for(make_member())
    assert len(c.get("/api/capabilities").json()) >= 40 and len(c.get("/api/traits").json()) >= 20


# -- profiles and IDOR -------------------------------------------------------------------
def test_member_profile_visible_and_other_people_cannot_edit_it(lists, make_member, client_for):
    a, b = make_member("founder"), make_member("student")
    client_for(a).put("/api/me/offers", json.dumps([{"capability": "seo"}]))
    r = client_for(b).get(f"/api/members/{a.pk}")
    assert r.status_code == 200 and r.json()["offers"][0]["capability"] == "seo"
    assert "auth_user_id" not in r.json()
    assert client_for(b).get("/api/me/offers").json() == []  # /me/* is always the caller's own data


@pytest.mark.parametrize("kw", [{"profile_visibility": "hidden"}, {"is_minor": True}, {"suspended_at": "now"}])
def test_hidden_minor_and_suspended_profiles_are_404(kw, make_member, client_for):
    from django.utils import timezone

    if kw.get("suspended_at"):
        kw = {"suspended_at": timezone.now()}
    target, viewer = make_member("founder", **kw), make_member("student")
    assert client_for(viewer).get(f"/api/members/{target.pk}").status_code == 404
    assert client_for(target).get(f"/api/members/{target.pk}").status_code in (200, 403)  # own profile (suspended: locked out)


def test_blocked_either_way_is_404(make_member, client_for):
    a, b = make_member("founder"), make_member("student")
    Block.objects.create(blocker=a, blocked=b)
    assert client_for(b).get(f"/api/members/{a.pk}").status_code == 404
    assert client_for(a).get(f"/api/members/{b.pk}").status_code == 404


def test_admin_accounts_are_not_browsable(make_member, make_org, client_for):
    admin = make_member("partner_admin", org=make_org())
    assert client_for(make_member("student")).get(f"/api/members/{admin.pk}").status_code == 404


# -- onboarding extraction ----------------------------------------------------------------
BIO = {"bio": "Second-year student who likes React and wants a mentor."}


def test_extraction_keeps_only_listed_slugs(lists, make_member, client_for, fake_llm):
    fake_llm.response = json.dumps(
        {
            "needs": ["mentoring", "made-up"],
            "offers": ["frontend-dev"],
            "skills": ["frontend-dev"],
            "traits": ["student-friendly", "x"],
        }
    )
    r = client_for(make_member()).post("/api/onboarding/extract", json.dumps(BIO))
    assert r.status_code == 200 and r.json()["source"] == "llm"
    assert r.json()["suggestions"] == {
        "needs": ["mentoring"], "offers": ["frontend-dev"], "skills": ["frontend-dev"], "traits": ["student-friendly"]
    }  # fmt: skip
    assert not Need.objects.exists()  # suggestions are not saved


def test_extraction_caps_each_list_at_five(lists, make_member, client_for, fake_llm):
    from apps.matching.models import Capability

    fake_llm.response = json.dumps({"needs": list(Capability.objects.values_list("slug", flat=True)[:9])})
    assert len(client_for(make_member()).post("/api/onboarding/extract", json.dumps(BIO)).json()["suggestions"]["needs"]) == 5


@pytest.mark.parametrize("response", ["not json", '{"needs": "mentoring"}', "[]"])
def test_bad_llm_output_falls_back_to_manual(response, lists, make_member, client_for, fake_llm):
    fake_llm.response = response
    r = client_for(make_member()).post("/api/onboarding/extract", json.dumps(BIO))
    assert r.status_code == 200 and r.json()["source"] == "manual" and r.json()["suggestions"]["needs"] == []


def test_llm_outage_falls_back_to_manual(lists, make_member, client_for, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    from core import llm

    llm.set_llm(FakeLLM(error=TimeoutError()))
    r = client_for(make_member()).post("/api/onboarding/extract", json.dumps(BIO))
    assert r.status_code == 200 and r.json()["source"] == "manual"


def test_extraction_is_rate_limited_and_validates_bio(lists, make_member, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "extraction": (2, 60)}
    c = client_for(make_member())
    assert c.post("/api/onboarding/extract", json.dumps({"bio": "short"})).status_code == 422
    assert c.post("/api/onboarding/extract", json.dumps({"bio": "x" * 2001})).status_code == 422
    assert c.post("/api/onboarding/extract", json.dumps(BIO)).status_code == 200
    assert c.post("/api/onboarding/extract", json.dumps(BIO)).status_code == 200
    assert c.post("/api/onboarding/extract", json.dumps(BIO)).status_code == 429


def test_extraction_prompt_lists_our_fixed_lists(lists, make_member, client_for, fake_llm):
    seen = {}
    fake_llm.complete = lambda system, user: seen.update(system=system, user=user) or "{}"  # type: ignore[method-assign]
    client_for(make_member()).post("/api/onboarding/extract", json.dumps(BIO))
    assert "frontend-dev" in seen["system"] and "deep-tech" in seen["system"] and seen["user"] == BIO["bio"]


# -- work email verification ---------------------------------------------------------------
def start(c, email="me@acme.io"):
    return c.post("/api/me/verify/work-email", json.dumps({"email": email}))


def test_work_email_flow_raises_level_to_2(make_member, client_for, settings):
    settings.ENV = "dev"
    m = make_member("mentor", level=1)
    c = client_for(m)
    r = start(c)
    assert r.status_code == 200 and len(r.json()["dev_code"]) == 8
    row = WorkEmailVerification.objects.get(member=m)
    assert row.email_domain == "acme.io" and "me@acme.io" not in str(row.__dict__)  # address never stored
    ok = c.post("/api/me/verify/work-email/confirm", json.dumps({"code": r.json()["dev_code"].lower()}))
    assert ok.status_code == 200 and ok.json()["verification_level"] == 2
    assert events("verification.level_raised").filter(actor=m).exists()


def test_code_not_returned_outside_dev_and_demo(make_member, client_for, settings):
    settings.ENV = "staging"
    assert start(client_for(make_member())).json()["dev_code"] is None


@pytest.mark.parametrize("email", ["me@gmail.com", "me@proton.me", "not-an-email", '"a b"@acme.io', "me@acme.ioK"])
def test_personal_or_invalid_emails_are_rejected(email, make_member, client_for):
    assert start(client_for(make_member()), email).status_code == 422


def test_wrong_code_five_times_locks_that_code(make_member, client_for, settings):
    settings.ENV = "dev"
    m = make_member(level=1)
    c = client_for(m)
    real = start(c).json()["dev_code"]
    for _ in range(5):
        assert c.post("/api/me/verify/work-email/confirm", json.dumps({"code": "WRONGONE"})).status_code == 400
    assert c.post("/api/me/verify/work-email/confirm", json.dumps({"code": real})).status_code == 400  # locked out now
    m.refresh_from_db()
    assert m.verification_level == 1


def test_expired_code_and_other_members_code_fail(make_member, client_for, settings):
    from datetime import timedelta

    from django.utils import timezone

    settings.ENV = "dev"
    a, b = make_member(level=1), make_member(level=1)
    code = start(client_for(a)).json()["dev_code"]
    assert client_for(b).post("/api/me/verify/work-email/confirm", json.dumps({"code": code})).status_code == 400  # IDOR
    WorkEmailVerification.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert client_for(a).post("/api/me/verify/work-email/confirm", json.dumps({"code": code})).status_code == 400


def test_already_level_2_conflict_and_never_lowered(make_member, client_for):
    m = make_member(level=3)
    assert start(client_for(m)).status_code == 409
    from apps.accounts.services import raise_level

    raise_level(m, 2, "x")
    m.refresh_from_db()
    assert m.verification_level == 3


def test_verification_start_is_rate_limited(make_member, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "verify": (2, 60)}
    c = client_for(make_member(level=1))
    assert start(c).status_code == 200 and start(c).status_code == 200 and start(c).status_code == 429


def test_code_helpers():
    code = codes.new_code()
    assert len(code) == 8 and codes.code_matches(code.lower(), codes.hash_code(code))
    assert not codes.code_matches("AAAAAAAA", codes.hash_code(code)) or code == "AAAAAAAA"
    assert codes.email_domain("A@Acme.IO") == "acme.io" and codes.email_domain("a@b@c.io") == ""
