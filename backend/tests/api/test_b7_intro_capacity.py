"""B7 part 1: GET /api/intros/capacity: what the intro sheet needs to say "2 left" before Send."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Connection
from apps.intros.models import IntroRequest

pytestmark = pytest.mark.django_db


def connect(x, y):
    Connection.objects.create(member_a_id=min(x.pk, y.pk), member_b_id=max(x.pk, y.pk), strength=0.9)


def test_a_fresh_member_has_the_full_allowance(make_member, client_for, settings):
    body = client_for(make_member("founder")).get("/api/intros/capacity").json()
    assert body == {
        "allowed": True,
        "weekly_limit": settings.INTRO_WEEKLY_LIMIT,
        "used": 0,
        "left": settings.INTRO_WEEKLY_LIMIT,
        "next_frees_at": None,
    }


def test_each_request_uses_one_and_the_last_one_says_when_the_next_frees_up(make_member, client_for, settings):
    me = make_member("founder")
    targets = [make_member("mentor") for _ in range(settings.INTRO_WEEKLY_LIMIT)]
    for t in targets:
        connect(me, t)
    c = client_for(me)
    for n, t in enumerate(targets, start=1):
        assert c.post("/api/intros", {"target_id": t.pk, "message": ""}).status_code == 201
        body = c.get("/api/intros/capacity").json()
        assert body["used"] == n and body["left"] == settings.INTRO_WEEKLY_LIMIT - n
        assert (body["next_frees_at"] is None) == (n < settings.INTRO_WEEKLY_LIMIT)
    oldest = IntroRequest.objects.filter(requester=me).order_by("created_at").first()
    assert c.get("/api/intros/capacity").json()["next_frees_at"][:19] == (oldest.created_at + timedelta(days=7)).isoformat()[:19]


def test_a_request_older_than_a_week_no_longer_counts(make_member, client_for, settings):
    me, t = make_member("founder"), make_member("mentor")
    connect(me, t)
    client_for(me).post("/api/intros", {"target_id": t.pk, "message": ""})
    IntroRequest.objects.update(created_at=timezone.now() - timedelta(days=8))
    assert client_for(me).get("/api/intros/capacity").json()["used"] == 0


def test_capacity_is_only_about_me(make_member, client_for):
    me, other, t = make_member("founder"), make_member("founder"), make_member("mentor")
    connect(other, t)
    client_for(other).post("/api/intros", {"target_id": t.pk, "message": ""})
    assert client_for(me).get("/api/intros/capacity").json()["used"] == 0


def test_the_numbers_agree_with_the_409(make_member, client_for, settings):
    me = make_member("founder")
    c = client_for(me)
    for _ in range(settings.INTRO_WEEKLY_LIMIT):
        t = make_member("mentor")
        connect(me, t)
        assert c.post("/api/intros", {"target_id": t.pk, "message": ""}).status_code == 201
    assert c.get("/api/intros/capacity").json()["left"] == 0
    extra = make_member("mentor")
    connect(me, extra)
    r = c.post("/api/intros", {"target_id": extra.pk, "message": ""})
    assert r.status_code == 409 and r.json()["error"]["code"] == "intro_weekly_limit"


def test_under_18_members_are_not_allowed_any(make_member, client_for):
    body = client_for(make_member("student", is_minor=True)).get("/api/intros/capacity").json()
    assert body["allowed"] is False and body["left"] == 0


def test_capacity_needs_sign_in(client):
    assert client.get("/api/intros/capacity").status_code == 401
