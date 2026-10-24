"""GET /api/invites: each beta member gets 3 single-use codes tied to them, logged as events."""

import pytest

from apps.beta.models import BetaAccess, InviteCode
from apps.events.models import Event

pytestmark = pytest.mark.django_db


def test_a_member_gets_three_codes_with_links(settings, make_member, client_for):
    settings.APP_URL = "https://app.example"
    m = make_member("founder")
    r = client_for(m).get("/api/invites")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 3 and {i["status"] for i in items} == {"available"}
    for i in items:
        assert i["link"] == f"https://app.example/join?code={i['code']}&src=invite"
    codes = InviteCode.objects.filter(created_by=m)
    assert codes.count() == 3
    assert all(c.kind == "member" and c.max_uses == 1 and c.expires_at is None and c.organisation_id is None for c in codes)
    assert Event.objects.filter(type="invite.created", actor=m).count() == 3


def test_calling_again_creates_nothing_new(make_member, client_for):
    m = make_member("student")
    c = client_for(m)
    first = c.get("/api/invites").json()
    assert c.get("/api/invites").json() == first
    assert InviteCode.objects.filter(created_by=m).count() == 3
    assert Event.objects.filter(type="invite.created").count() == 3


def test_raising_the_limit_tops_everyone_up_and_lowering_takes_nothing_away(settings, make_member, client_for):
    m = make_member("student")
    c = client_for(m)
    c.get("/api/invites")
    settings.INVITES_PER_MEMBER = 5
    assert len(c.get("/api/invites").json()["items"]) == 5
    settings.INVITES_PER_MEMBER = 2
    assert len(c.get("/api/invites").json()["items"]) == 5


def test_zero_means_no_invites(settings, make_member, client_for):
    settings.INVITES_PER_MEMBER = 0
    assert client_for(make_member("student")).get("/api/invites").json() == {"items": []}


def test_a_revoked_code_is_not_replaced_for_free(make_member, client_for):
    from apps.beta import services

    m = make_member("student")
    c = client_for(m)
    first = c.get("/api/invites").json()["items"][0]
    services.revoke_code(InviteCode.objects.get(code=first["code"]))
    items = c.get("/api/invites").json()["items"]
    assert len(items) == 3 and [i["status"] for i in items].count("revoked") == 1


def test_a_member_code_works_once_and_shows_as_used(beta_on, make_member, client_for, let_in):
    inviter, friend, second = make_member("student"), make_member("student"), make_member("student")
    let_in(inviter)
    code = client_for(inviter).get("/api/invites").json()["items"][0]["code"]
    assert client_for(friend).post("/api/beta/redeem", {"code": code}).status_code == 200
    assert client_for(second).post("/api/beta/redeem", {"code": code}).status_code == 400
    assert [i["status"] for i in client_for(inviter).get("/api/invites").json()["items"]].count("used") == 1
    granted = Event.objects.get(type="beta.access_granted", actor=friend)
    assert granted.payload == {"source": "code", "inviter_id": inviter.pk}  # the inviter is logged


def test_nobody_sees_anyone_elses_codes(make_member, client_for):
    a, b = make_member("student"), make_member("student")
    mine = {i["code"] for i in client_for(a).get("/api/invites").json()["items"]}
    theirs = {i["code"] for i in client_for(b).get("/api/invites").json()["items"]}
    assert mine.isdisjoint(theirs) and len(mine) == len(theirs) == 3


def test_an_outsider_cannot_list_invites_while_the_beta_is_on(beta_on, make_member, client_for):
    r = client_for(make_member("student")).get("/api/invites")
    assert r.status_code == 403 and r.json()["error"]["code"] == "beta_required"
    assert not InviteCode.objects.exists()


def test_codes_come_from_a_wide_alphabet_and_are_distinct(make_member):
    from apps.beta import services
    from core.codes import ALPHABET

    codes = [services.create_code().code for _ in range(50)]
    assert len(set(codes)) == 50
    assert all(len(c) == 10 and set(c) <= set(ALPHABET) for c in codes)
    assert BetaAccess.objects.count() == 0
