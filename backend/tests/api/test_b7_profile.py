"""B7 part 1: GET /api/members/{id} is the whole Profile screen: header, actions, mutuals, build logs, circuits, strength."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import ConnectionRequest
from apps.circuits.models import Circuit, CircuitLeg, CircuitRound
from apps.matching.models import Capability, MemberSkill, Need, Offer
from apps.social.models import MediaUpload, Post, PostMedia
from core.storage import get_storage

pytestmark = pytest.mark.django_db


def profile(client, member):
    r = client.get(f"/api/members/{member.pk}")
    assert r.status_code == 200, r.content
    return r.json()


def closed_circuit(*members):
    rnd = CircuitRound.objects.create(week=f"2026-W{40 + Circuit.objects.count()}")
    c = Circuit.objects.create(round=rnd, status="completed", score=0.9, consent_deadline=timezone.now() + timedelta(days=1))
    cap = Capability.objects.first()
    for giver, receiver in zip(members, members[1:] + members[:1]):
        CircuitLeg.objects.create(circuit=c, giver=giver, receiver=receiver, capability=cap)
    return c


def picture_post(author, visibility="everyone"):
    post = Post.objects.create(author=author, body="Shipped", visibility=visibility)
    up = MediaUpload.objects.create(
        owner=author, purpose="post", path=f"post/{author.pk}/{post.pk}", status="ready", width=9, height=9
    )
    get_storage().put("posts", f"{up.path}/w480.webp", b"x", "image/webp")
    PostMedia.objects.create(post=post, upload=up, alt_text="a screen", order=0)
    return post


# -- header ----------------------------------------------------------------------------------------
def test_the_header_and_card_fields(lists, make_member, client_for):
    viewer, target = make_member("student"), make_member("mentor", display_name="Lakshmi", bio="Mentor for B2B sales. " * 20)
    body = profile(client_for(viewer), target)
    assert body["is_me"] is False and body["photo"] is None
    assert body["headline"] == target.bio.strip()[:140] and body["organisation"] is None
    assert body["connection"] == "none" and body["strength"] is None and body["circuits_closed"] is None


def test_the_organisation_is_shown_to_people_in_it_only(make_member, make_org, client_for):
    org = make_org("SVIT")
    target = make_member("student", org=org)
    assert profile(client_for(make_member("student", org=org)), target)["organisation"] == "SVIT"
    assert profile(client_for(make_member("student")), target)["organisation"] is None
    assert profile(client_for(target), target)["organisation"] == "SVIT"


def test_there_are_no_follower_or_connection_counts(make_member, connect, client_for):
    viewer, target, friend = make_member("student"), make_member("mentor"), make_member("mentor")
    connect(viewer, friend)
    connect(target, friend)
    body = profile(client_for(viewer), target)
    assert body["mutual_count"] == 1
    for word in ("follower", "connection_count", "connections_count", "friends"):
        assert word not in str(body).lower()
    assert profile(client_for(target), target)["mutual_count"] is None  # nothing to compare on my own profile


# -- connection state and actions ----------------------------------------------------------------------
def test_a_stranger_can_be_asked_to_connect_and_messaged(make_member, client_for):
    viewer, target = make_member("student"), make_member("founder")
    body = profile(client_for(viewer), target)
    assert body["connection"] == "none" and body["actions"] == {"connect": True, "message": True, "intro": False}


def test_connection_states(make_member, connect, client_for):
    me, friend, asked, asker = (make_member("student") for _ in range(4))
    connect(me, friend)
    ConnectionRequest.objects.create(sender=me, recipient=asked)
    ConnectionRequest.objects.create(sender=asker, recipient=me)
    c = client_for(me)
    assert profile(c, friend)["connection"] == "connected" and profile(c, friend)["actions"]["connect"] is False
    assert profile(c, asked)["connection"] == "requested" and profile(c, asked)["actions"]["connect"] is False
    assert profile(c, asker)["connection"] == "requested_you" and profile(c, asker)["actions"]["connect"] is True
    assert profile(c, me)["connection"] == "self" and profile(c, me)["actions"] == {
        "connect": False,
        "message": False,
        "intro": False,
    }


def test_a_declined_request_looks_like_none_and_is_not_offered_again(make_member, client_for):
    me, target = make_member("student"), make_member("mentor")
    ConnectionRequest.objects.create(sender=me, recipient=target, status="declined", responded_at=timezone.now())
    body = profile(client_for(me), target)
    assert body["connection"] == "none" and body["actions"]["connect"] is False  # never says "declined"
    assert "declined" not in str(body)


def test_closed_to_strangers_means_no_connect_or_message(make_member, client_for):
    target = make_member("mentor", allow_requests=False)
    assert profile(client_for(make_member("student")), target)["actions"] == {"connect": False, "message": False, "intro": False}


def test_a_warm_path_gives_the_intro_action_and_the_mutual(make_member, connect, client_for):
    me, broker, target = make_member("student"), make_member("mentor", display_name="Meera"), make_member("investor")
    connect(me, broker)
    connect(broker, target)
    body = profile(client_for(me), target)
    assert body["via"]["display_name"] == "Meera" and body["actions"]["intro"] is True and body["mutual_count"] == 1


def test_a_connected_person_needs_no_intro(make_member, connect, client_for):
    me, target = make_member("student"), make_member("investor")
    connect(me, target)
    body = profile(client_for(me), target)
    assert body["via"] is None and body["actions"]["intro"] is False


def test_under_18s_never_get_an_intro_path(make_member, connect, client_for):
    kid, broker, target = make_member("student", is_minor=True), make_member("mentor"), make_member("mentor")
    connect(kid, broker)
    connect(broker, target)
    body = profile(client_for(kid), target)
    assert body["via"] is None and body["actions"]["intro"] is False


# -- build logs -------------------------------------------------------------------------------------
def test_the_build_log_grid_shows_only_posts_the_viewer_may_see(make_member, connect, client_for):
    target, friend, stranger = make_member("founder"), make_member("student"), make_member("student")
    connect(target, friend)
    shown = picture_post(target, "everyone")
    private = picture_post(target, "connections")
    assert [t["post_id"] for t in profile(client_for(stranger), target)["build_logs"]] == [shown.pk]
    assert sorted(t["post_id"] for t in profile(client_for(friend), target)["build_logs"]) == sorted([shown.pk, private.pk])
    tile = profile(client_for(stranger), target)["build_logs"][0]
    assert tile["image"]["alt_text"] == "a screen" and tile["image"]["w480"].startswith("http")


def test_the_grid_is_empty_with_pulse_off(make_member, client_for, settings):
    from core import flags

    target = make_member("founder")
    picture_post(target)
    settings.FEATURES = ",".join(f"{n}:{'everyone' if n in ('circuits', 'daily_drop') else 'off'}" for n in flags.FLAGS)
    assert profile(client_for(make_member("student")), target)["build_logs"] == []


# -- circuits -----------------------------------------------------------------------------------------
def test_closed_circuits_are_counted_for_me_and_my_connections_only(make_member, connect, client_for):
    a, b, c = make_member("student"), make_member("founder"), make_member("mentor")
    closed_circuit(a, b, c)
    friend, stranger = make_member("student"), make_member("student")
    connect(a, friend)
    assert profile(client_for(a), a)["circuits_closed"] == 1
    assert profile(client_for(friend), a)["circuits_closed"] == 1
    assert profile(client_for(stranger), a)["circuits_closed"] is None


def test_circuit_counts_are_hidden_with_circuits_off(make_member, client_for, settings):
    from core import flags

    a, b, c = make_member("student"), make_member("founder"), make_member("mentor")
    closed_circuit(a, b, c)
    settings.FEATURES = ",".join(f"{n}:{'off' if n == 'circuits' else 'everyone'}" for n in flags.FLAGS if n not in ("payments",))
    settings.FEATURES += ",payments:off"
    assert profile(client_for(a), a)["circuits_closed"] is None


# -- strength: the owner only -------------------------------------------------------------------------
def test_strength_is_for_the_owner_and_names_one_next_step(lists, make_member, client_for):
    me = make_member("student", bio="")
    body = profile(client_for(me), me)["strength"]
    assert body["next_step"] == {"key": "photo", "text": "Add a photo"} and body["percent"] == 0
    assert profile(client_for(make_member("student")), me)["strength"] is None  # nobody else sees the meter


def test_strength_climbs_as_the_profile_fills_in(lists, make_member, client_for):
    me = make_member("student", bio="I build small tools for local shops and teach SQL on weekends.", level=2)
    me.photo_path = "avatar/1/x"
    me.save()
    Offer.objects.create(member=me, capability=Capability.objects.first())
    Need.objects.create(member=me, capability=Capability.objects.last())
    s = profile(client_for(me), me)["strength"]
    assert s["next_step"]["key"] == "headline" and s["percent"] == 63  # 5 of the 8 steps are done
    me.headline = "Student, building tools for local shops"
    me.save()
    s = profile(client_for(me), me)["strength"]
    assert s["next_step"]["key"] == "skills" and s["percent"] == 75  # 6 of 8
    MemberSkill.objects.create(member=me, capability=Capability.objects.first(), level=2, proof_url="https://example.com/a")
    picture_post(me)
    assert profile(client_for(me), me)["strength"] == {"percent": 100, "next_step": None}


# -- who can be seen at all -----------------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["hidden", "minor", "suspended", "admin"])
def test_people_who_must_not_be_seen_are_a_404(make_member, client_for, kind):
    kw = {"hidden": {"profile_visibility": "hidden"}, "minor": {"is_minor": True}, "suspended": {"suspended_at": timezone.now()}}
    target = make_member("partner_admin" if kind == "admin" else "mentor", **kw.get(kind, {}))
    assert client_for(make_member("student")).get(f"/api/members/{target.pk}").status_code == 404


def test_a_blocked_person_is_a_404_both_ways(make_member, block, client_for):
    a, b = make_member("student"), make_member("mentor")
    block(a, b)
    assert client_for(a).get(f"/api/members/{b.pk}").status_code == 404
    assert client_for(b).get(f"/api/members/{a.pk}").status_code == 404


def test_my_own_under_18_profile_works_for_me(make_member, client_for):
    kid = make_member("student", is_minor=True)
    body = profile(client_for(kid), kid)
    assert body["is_me"] is True and body["connection"] == "self"
