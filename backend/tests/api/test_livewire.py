"""The Live wire (F16): 24 hours, five kinds, relevance order, the usual visibility rules, no counts."""

from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.events.services import record
from apps.jobs.models import Job, JobCapability
from apps.matching.models import Capability, MemberSkill, Need, Offer
from apps.social.models import Follow, Post, UpdateView
from apps.startups.models import StartupMember

pytestmark = pytest.mark.django_db


def age(post, **delta):
    Post.objects.filter(pk=post.pk).update(created_at=timezone.now() - timedelta(**delta))
    return post


def wire(client_for, member):
    r = client_for(member).get("/api/livewire")
    assert r.status_code == 200
    return r.json()


@pytest.fixture
def me_and_friend(make_member, connect):
    me = make_member("student", display_name="Me", location=Point(80.27, 13.08, srid=4326))
    friend = make_member("founder", display_name="Friend", location=Point(80.28, 13.09, srid=4326))
    connect(me, friend)
    return me, friend


def test_shipped_shows_a_connections_newest_build_log_with_a_reason(me_and_friend, make_post, lists, client_for):
    me, friend = me_and_friend
    cap = Capability.objects.get(slug="frontend-dev")
    MemberSkill.objects.create(member=me, capability=cap)
    old, new = make_post(friend, body="older"), make_post(friend, body="Shipped the checkout screen")
    old.capabilities.set([cap])
    new.capabilities.set([cap])
    age(old, hours=3)
    items = wire(client_for, me)
    assert [i["key"] for i in items] == [f"post:{new.pk}"]  # one node per person
    i = items[0]
    assert i["kind"] == "shipped" and i["headline"] == "Shipped the checkout screen" and i["seen"] is False
    assert i["actor"]["id"] == friend.pk and i["action"] == {"kind": "intro", "target_id": friend.pk}
    assert "Frontend" in i["reason"] and "km away" in i["reason"]


def test_only_the_last_24_hours_and_only_what_i_may_see(me_and_friend, make_member, make_post, block, client_for):
    me, friend = me_and_friend
    stranger = make_member("mentor", display_name="Stranger")
    blocked = make_member("founder", display_name="Blocked")
    block(me, blocked)
    age(make_post(friend, body="yesterday"), hours=30)
    make_post(stranger, body="not mine")
    make_post(blocked, body="blocked")
    make_post(friend, "organisation", body="friend has no organisation")
    assert wire(client_for, me) == []


def test_hiring_needs_joined_and_circuit_nodes(me_and_friend, make_member, make_org, make_startup, lists, client_for):
    me, friend = me_and_friend
    startup = make_startup(claimed_by=friend)
    StartupMember.objects.create(startup=startup, member=friend)
    Follow.objects.create(member=me, startup=startup)
    seo = Capability.objects.get(slug="seo")
    job = Job.objects.create(startup=startup, title="SEO intern", kind="internship", description="x", posted_by=friend)
    JobCapability.objects.create(job=job, capability=seo, required=True)
    Offer.objects.create(member=me, capability=seo)
    Need.objects.create(member=friend, capability=seo, description="someone to fix our SEO")
    org = make_org()
    me.organisation = org
    me.save()
    mate = make_member("student", org=org, display_name="Mate")
    record("org.joined", actor=mate, target_type="organisation", target_id=org.pk, method="code")
    by_kind = {i["kind"]: i for i in wire(client_for, me)}
    assert set(by_kind) == {"hiring", "needs", "joined"}
    assert by_kind["hiring"]["startup"]["id"] == startup.pk and by_kind["hiring"]["actor"] is None
    assert by_kind["hiring"]["action"] == {"kind": "view_role", "target_id": job.pk}
    assert by_kind["needs"]["headline"].startswith("Needs help with") and "which they need" in by_kind["needs"]["reason"]
    assert by_kind["joined"]["headline"] == f"Joined {org.name}"


def test_most_relevant_first_and_unseen_before_seen(me_and_friend, make_member, make_post, connect, lists, client_for):
    me, friend = me_and_friend
    other = make_member("founder", display_name="Other")
    connect(me, other)
    cap = Capability.objects.get(slug="seo")
    Need.objects.create(member=me, capability=cap)
    a, b = make_post(friend, body="plain"), make_post(other, body="about SEO")
    b.capabilities.set([cap])
    first = [i["key"] for i in wire(client_for, me)]
    assert first == [f"post:{b.pk}", f"post:{a.pk}"]  # the one that matches what I need leads
    assert client_for(me).post("/api/livewire/seen", {"key": f"post:{b.pk}"}).status_code == 204
    after = wire(client_for, me)
    assert [i["key"] for i in after] == [f"post:{a.pk}", f"post:{b.pk}"] and [i["seen"] for i in after] == [False, True]
    assert client_for(me).post("/api/livewire/seen", {"key": f"post:{b.pk}"}).status_code == 204  # safe to repeat
    assert UpdateView.objects.filter(viewer=me).count() == 1


def test_a_key_that_is_not_on_my_wire_is_a_404(me_and_friend, make_member, make_post, client_for):
    me, _ = me_and_friend
    stranger_post = make_post(make_member("mentor", display_name="Stranger"), body="private to strangers")
    for key in (f"post:{stranger_post.pk}", "post:999999", "nonsense"):
        assert client_for(me).post("/api/livewire/seen", {"key": key}).status_code == 404
    assert UpdateView.objects.count() == 0


def test_no_counts_and_at_most_six_of_one_kind(make_member, make_post, connect, client_for):
    me = make_member("student", display_name="Me")
    for n in range(15):
        friend = make_member("founder", display_name=f"F{n}")
        connect(me, friend)
        make_post(friend, body=f"post {n}")
    items = wire(client_for, me)
    assert len(items) == 6  # up to 12 overall, but one kind never fills the wire
    assert set(items[0]) == {"key", "kind", "actor", "startup", "image", "headline", "reason", "action", "created_at", "seen"}


def test_under_18s_do_not_appear_as_needs_or_joins_for_others(make_member, make_org, connect, lists, client_for):
    org = make_org()
    me = make_member("student", org=org, display_name="Me")
    minor = make_member("student", org=org, is_minor=True, display_name="Minor")
    connect(me, minor)
    Need.objects.create(member=minor, capability=Capability.objects.get(slug="seo"))
    record("org.joined", actor=minor, target_type="organisation", target_id=org.pk, method="code")
    assert wire(client_for, me) == []


def test_one_kind_cannot_fill_the_wire(make_member, connect, lists, client_for):
    me = make_member("student", display_name="Me")
    for n in range(8):
        other = make_member("student", display_name=f"S{n}")
        connect(me, other)
        Need.objects.create(member=other, capability=Capability.objects.get(slug="seo"))
    assert [i["kind"] for i in wire(client_for, me)] == ["needs"] * 3
