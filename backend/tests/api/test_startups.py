import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.models import Event
from apps.jobs.models import Job, JobCapability
from apps.matching.models import Capability, MemberSkill
from apps.startups.models import ClaimRequest, Startup, StartupInterest, StartupMember

pytestmark = pytest.mark.django_db
CHENNAI = (13.0827, 80.2707)


def pins(r):
    assert r.status_code == 200, r.content
    return r.json()


def nearby(client, **q):
    q = {"lat": CHENNAI[0], "lng": CHENNAI[1], **q}
    return client.get("/api/startups/nearby?" + "&".join(f"{k}={v}" for k, v in q.items()))


def add_job(startup, caps, required_first=True):
    job = Job.objects.create(startup=startup, title="Intern", is_open=True)
    for i, slug in enumerate(caps):
        JobCapability.objects.create(
            job=job, capability=Capability.objects.get(slug=slug), required=(i == 0) if required_first else False
        )
    return job


# -- nearby and map ---------------------------------------------------------------------
def test_nearby_orders_by_distance_and_applies_radius(make_member, make_startup, client_for):
    near = make_startup("Near", "near.io", 13.09, 80.28)
    mid = make_startup("Mid", "mid.io", 13.15, 80.27)  # ~7.5 km
    make_startup("Far", "far.io", 12.5, 80.0)  # ~65 km
    out = pins(nearby(client_for(make_member()), radius_km=10))
    assert [p["id"] for p in out] == [near.pk, mid.pk]
    assert out[0]["distance_km"] < out[1]["distance_km"] < 10
    assert len(pins(nearby(client_for(make_member()), radius_km=100))) == 3


def test_nearby_filters_hiring_and_capability(lists, make_member, make_startup, client_for):
    hiring = make_startup("H", "h.io", hiring=True)
    quiet = make_startup("Q", "q.io")
    add_job(hiring, ["frontend-dev"])
    c = client_for(make_member())
    assert [p["id"] for p in pins(nearby(c, hiring="true"))] == [hiring.pk]
    assert [p["id"] for p in pins(nearby(c, hiring="false"))] == [quiet.pk]
    assert [p["id"] for p in pins(nearby(c, capability="frontend-dev"))] == [hiring.pk]
    assert pins(nearby(c, capability="seo")) == []


def test_nearby_defaults_to_my_location(make_member, make_startup, client_for):
    from django.contrib.gis.geos import Point

    make_startup("Chennai", "c.io", 13.08, 80.27)
    far_member = make_member(location=Point(77.59, 12.97, srid=4326))  # Bengaluru: nothing within 10 km
    assert pins(client_for(far_member).get("/api/startups/nearby")) == []
    assert len(pins(client_for(make_member()).get("/api/startups/nearby"))) == 1  # no location: city centre


def test_nearby_validates_params(make_member, client_for):
    c = client_for(make_member())
    assert nearby(c, radius_km=0).status_code == 422
    assert nearby(c, radius_km=101).status_code == 422
    assert nearby(c, lat=95).status_code == 422


def test_unlocated_startups_are_never_listed(make_member, client_for):
    Startup.objects.create(name="Nowhere", website_domain="nowhere.io")
    assert pins(nearby(client_for(make_member()))) == []


def test_map_returns_pins_in_box_hiring_first(make_member, make_startup, client_for):
    a = make_startup("A", "a.io", 13.0, 80.2)
    b = make_startup("B", "b.io", 13.1, 80.3, hiring=True)
    make_startup("Out", "out.io", 20.0, 70.0)
    r = client_for(make_member()).get("/api/startups/map?min_lng=80&min_lat=12.9&max_lng=80.5&max_lat=13.3")
    assert [p["id"] for p in pins(r)] == [b.pk, a.pk]


@pytest.mark.parametrize(
    "q,code",
    [
        ("min_lng=80&min_lat=13&max_lng=83&max_lat=14", "bbox_too_large"),
        ("min_lng=81&min_lat=13&max_lng=80&max_lat=14", "invalid_bbox"),
    ],
)
def test_map_rejects_huge_or_inverted_boxes(q, code, make_member, client_for):
    r = client_for(make_member()).get(f"/api/startups/map?{q}")
    assert r.status_code == 422 and r.json()["error"]["code"] == code


def test_map_caps_pins_at_500(make_member, make_startup, client_for, monkeypatch):
    from apps.startups import services

    monkeypatch.setattr(services, "MAX_PINS", 3)
    for i in range(5):
        make_startup(f"S{i}", f"s{i}.io")
    assert len(pins(client_for(make_member()).get("/api/startups/map?min_lng=80&min_lat=13&max_lng=80.5&max_lat=13.3"))) == 3


def test_student_sees_skill_match_pct_others_do_not(lists, make_member, make_startup, client_for):
    s = make_startup("Px", "px.io", hiring=True)
    add_job(s, ["frontend-dev", "ui-design"])  # frontend required, ui optional
    student = make_member("student")
    MemberSkill.objects.create(member=student, capability=Capability.objects.get(slug="frontend-dev"), level=3)
    assert pins(nearby(client_for(student)))[0]["match_pct"] == 80
    assert pins(nearby(client_for(make_member("founder"))))[0]["match_pct"] is None
    assert pins(nearby(client_for(student)))[0]["open_roles"] == 1


def test_match_pct_is_none_without_open_roles(make_member, make_startup, client_for):
    make_startup("Nojob", "nojob.io")
    assert pins(nearby(client_for(make_member("student"))))[0]["match_pct"] is None


# -- detail, views, interest ---------------------------------------------------------------
def test_detail_counts_one_view_per_member_per_day(make_member, make_startup, client_for):
    s = make_startup()
    a, b = make_member("student"), make_member("student")
    for _ in range(3):
        assert client_for(a).get(f"/api/startups/{s.pk}").status_code == 200
    r = client_for(b).get(f"/api/startups/{s.pk}")
    assert r.json()["view_count"] is None  # students never see the count (see test_b7_startup_page.py)
    s.refresh_from_db()
    assert s.view_count == 2
    assert Event.objects.filter(type="startup.viewed", target_id=s.pk).count() == 2


def test_view_still_counts_when_redis_is_down(make_member, make_startup, client_for, monkeypatch):
    from core import cache

    monkeypatch.setattr(cache.Cache, "incr_window", lambda self, key, window: None)
    s = make_startup()
    assert client_for(make_member()).get(f"/api/startups/{s.pk}").status_code == 200
    s.refresh_from_db()
    assert s.view_count == 1


def test_team_views_do_not_count(make_member, make_startup, client_for):
    owner = make_member("founder")
    s = make_startup(claimed_by=owner)
    StartupMember.objects.create(startup=s, member=owner)
    r = client_for(owner).get(f"/api/startups/{s.pk}")
    assert r.json()["view_count"] == 0 and r.json()["is_team"] is True


def test_detail_shows_open_jobs_interest_and_claimed_flag(lists, make_member, make_startup, client_for):
    s = make_startup(hiring=True)
    job = add_job(s, ["seo"])
    Job.objects.create(startup=s, title="Closed", is_open=False)
    student = make_member("student")
    client_for(student).post(f"/api/startups/{s.pk}/interest")
    body = client_for(student).get(f"/api/startups/{s.pk}").json()
    assert [j["id"] for j in body["open_jobs"]] == [job.pk]
    assert StartupInterest.objects.filter(startup=s).count() == 1
    assert body["interest_count"] is None and body["interested"] is True and body["claimed"] is False  # the count is private


def test_unknown_startup_is_404(make_member, client_for):
    assert client_for(make_member()).get("/api/startups/999999").status_code == 404


def test_interest_is_idempotent_and_reversible(make_member, make_startup, client_for):
    s, student = make_startup(), make_member("student")
    c = client_for(student)
    assert c.post(f"/api/startups/{s.pk}/interest").status_code == 204
    assert c.post(f"/api/startups/{s.pk}/interest").status_code == 204
    assert StartupInterest.objects.filter(startup=s).count() == 1
    assert Event.objects.filter(type="startup.interest_added").count() == 1
    assert c.delete(f"/api/startups/{s.pk}/interest").status_code == 204
    assert c.delete(f"/api/startups/{s.pk}/interest").status_code == 204
    assert not StartupInterest.objects.exists() and Event.objects.filter(type="startup.interest_removed").count() == 1


def test_only_students_can_show_interest(make_member, make_startup, client_for):
    s = make_startup()
    assert client_for(make_member("founder")).post(f"/api/startups/{s.pk}/interest").status_code == 403
    assert client_for(make_member("student")).post("/api/startups/999999/interest").status_code == 404


# -- editing ----------------------------------------------------------------------------------
def test_team_can_edit_claimed_startup(make_member, make_startup, client_for):
    owner = make_member("founder")
    s = make_startup(claimed_by=owner)
    StartupMember.objects.create(startup=s, member=owner)
    r = client_for(owner).patch(
        f"/api/startups/{s.pk}", json.dumps({"description": "New", "hiring": True, "lat": 13.0, "lng": 80.0})
    )
    assert r.status_code == 200 and r.json()["description"] == "New" and r.json()["hiring"] is True and r.json()["lat"] == 13.0
    assert Event.objects.filter(type="startup.updated", actor=owner).exists()


def test_non_team_cannot_edit_even_another_founder_or_an_unclaimed_startup(make_member, make_startup, client_for):
    owner, other = make_member("founder"), make_member("founder")
    claimed = make_startup(claimed_by=owner)
    StartupMember.objects.create(startup=claimed, member=owner)
    unclaimed = make_startup("U", "u.io")
    body = json.dumps({"description": "hacked"})
    assert client_for(other).patch(f"/api/startups/{claimed.pk}", body).status_code == 403
    assert client_for(owner).patch(f"/api/startups/{unclaimed.pk}", body).status_code == 403
    assert client_for(owner).patch("/api/startups/999999", body).status_code == 404
    claimed.refresh_from_db()
    assert claimed.description != "hacked"


def test_edit_cannot_touch_name_domain_or_claim(make_member, make_startup, client_for):
    owner = make_member("founder")
    s = make_startup(claimed_by=owner)
    StartupMember.objects.create(startup=s, member=owner)
    client_for(owner).patch(f"/api/startups/{s.pk}", json.dumps({"name": "X", "website_domain": "evil.io", "claimed_by": 5}))
    s.refresh_from_db()
    assert s.name == "Acme" and s.website_domain == "acme.io" and s.claimed_by_id == owner.pk


# -- claim flow ------------------------------------------------------------------------------------
def claim(c, s, email="me@acme.io"):
    return c.post(f"/api/startups/{s.pk}/claim", json.dumps({"email": email}))


def verify(c, s, code):
    return c.post(f"/api/startups/{s.pk}/claim/verify", json.dumps({"code": code}))


def test_claim_happy_path(make_member, make_startup, client_for, settings):
    settings.ENV = "dev"
    s, f = make_startup(), make_member("founder", level=1)
    c = client_for(f)
    code = claim(c, s, "Priya@Mail.Acme.io").json()["dev_code"]  # subdomain and mixed case both fine
    r = verify(c, s, code)
    assert r.status_code == 200 and r.json()["claimed"] is True and r.json()["is_team"] is True
    s.refresh_from_db()
    f.refresh_from_db()
    assert s.claimed_by_id == f.pk and s.claimed_at and f.verification_level == 2
    assert StartupMember.objects.filter(startup=s, member=f).exists()
    types = set(Event.objects.values_list("type", flat=True))
    assert {"startup.claim_started", "startup.claimed", "verification.level_raised"} <= types
    assert "acme.io" in ClaimRequest.objects.get().email_domain and "Priya" not in str(ClaimRequest.objects.values())


@pytest.mark.parametrize("email", ["me@gmail.com", "me@acme.io.evil.com", "me@notacme.io", "me@evilacme.io", "me@аcme.io", "x"])
def test_claim_needs_an_email_at_the_startups_domain(email, make_member, make_startup, client_for):
    r = claim(client_for(make_member("founder")), make_startup(), email)
    assert r.status_code == 422, email


def test_claim_is_founders_only(make_member, make_startup, client_for):
    assert claim(client_for(make_member("student")), make_startup()).status_code == 403
    assert verify(client_for(make_member("mentor")), make_startup("B", "b.io"), "ABCDEFGH").status_code == 403


def test_already_claimed_startup_cannot_be_claimed_again(make_member, make_startup, client_for):
    owner = make_member("founder")
    s = make_startup(claimed_by=owner)
    assert claim(client_for(make_member("founder")), s).status_code == 409
    assert verify(client_for(make_member("founder")), s, "ABCDEFGH").status_code == 409


def test_wrong_expired_or_someone_elses_code_fails(make_member, make_startup, client_for, settings):
    settings.ENV = "dev"
    s, f, thief = make_startup(), make_member("founder"), make_member("founder")
    code = claim(client_for(f), s).json()["dev_code"]
    assert verify(client_for(f), s, "WRONGONE").status_code == 400
    assert verify(client_for(thief), s, code).status_code == 400  # IDOR: the code belongs to f's request only
    ClaimRequest.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert verify(client_for(f), s, code).status_code == 400
    s.refresh_from_db()
    assert s.claimed_by_id is None


def test_code_cannot_be_used_on_another_startup(make_member, make_startup, client_for, settings):
    settings.ENV = "dev"
    s1, s2, f = make_startup(), make_startup("Two", "two.io"), make_member("founder")
    code = claim(client_for(f), s1).json()["dev_code"]
    assert verify(client_for(f), s2, code).status_code == 400


def test_new_claim_replaces_old_pending_code(make_member, make_startup, client_for, settings):
    settings.ENV = "dev"
    s, f = make_startup(), make_member("founder")
    old = claim(client_for(f), s).json()["dev_code"]
    new = claim(client_for(f), s).json()["dev_code"]
    assert verify(client_for(f), s, old).status_code == 400
    assert verify(client_for(f), s, new).status_code == 200


def test_claim_is_rate_limited(make_member, make_startup, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "claim": (2, 60)}
    s, c = make_startup(), client_for(make_member("founder"))
    assert claim(c, s).status_code == 200 and claim(c, s).status_code == 200 and claim(c, s).status_code == 429
    assert verify(c, s, "ABCDEFGH").status_code == 429


def test_expire_claims_marks_old_requests(make_member, make_startup):
    from apps.startups.services import expire_claims

    s, f = make_startup(), make_member("founder")
    ClaimRequest.objects.create(
        startup=s, member=f, email_domain="acme.io", token_hash="x", expires_at=timezone.now() - timedelta(hours=1)
    )
    assert expire_claims() == 1 and ClaimRequest.objects.get().status == "expired"
