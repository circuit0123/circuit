"""Stage 6: blocking a member. It works both ways and removes the other person from matches, Daily Drop, Pulse, Live wire, intros,
circuits, Inbox, notifications and profiles. Every surface is checked BEFORE the block (the person is there) and AFTER, both ways."""

import pytest
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Connection, ConnectionRequest
from apps.circuits.models import Circuit
from apps.events.models import Event
from apps.intros.models import IntroRequest
from apps.matching import services as matching
from apps.matching.models import MatchResult
from apps.messaging.models import Conversation
from apps.moderation.models import Block
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.social.drop import build_all, drop_day
from apps.social.models import DailyDrop
from tests.api.test_circuits import make_loop
from tests.api.test_circuits import propose as propose_circuit

pytestmark = pytest.mark.django_db
HERE = Point(80.27, 13.08, srid=4326)


@pytest.fixture
def world(lists, make_member, connect, make_post, client_for):
    """a and b are connected and talk; they match; they each posted; a asked b for an intro; with c they form a circuit."""
    a, b, c = make_loop(make_member, location=HERE)
    a.display_name, b.display_name, c.display_name = "Asha", "Priya", "Arjun"
    for m in (a, b, c):
        m.save()
    connect(a, b)
    matching.compute_all()
    posts = {a.pk: make_post(a, body="Asha shipped the login screen"), b.pk: make_post(b, body="Priya closed the seed round")}
    conv = client_for(a).post("/api/conversations", {"member_id": b.pk, "body": "hello Priya"}).json()["conversation"]["id"]
    assert client_for(a).post("/api/intros", {"target_id": b.pk, "message": "can we talk?"}).status_code == 201
    circuit = propose_circuit((a, b, c))
    today = drop_day(timezone.now())
    for me, other in ((a, b), (b, a)):  # a drop that already holds the other person, as it would after the 08:00 job
        card = {"member_id": other.pk, "reason": "shared", "is_bridge": False, "outcome": None, "strength": "good"}
        DailyDrop.objects.create(member=me, date=today, candidates=[card])
    notify(a, "intro.accepted", actor=b, intro_id=1)  # something b did that a was told about
    notify(b, "intro.accepted", actor=a, intro_id=1)
    return {"a": a, "b": b, "c": c, "posts": posts, "conv": conv, "circuit": circuit}


def seen_by(client_for, who, other, w):
    """Every surface where `who` could see `other`, as {surface: bool}."""
    c = client_for(who)
    pulse = c.get("/api/pulse?include_seen=true").json()["items"]
    return {
        "matches": other.pk in {m["candidate_id"] for m in c.get("/api/matches").json()["items"]},
        "drop": other.pk in {card["member"]["id"] for card in c.get("/api/drop/today").json()["cards"]},
        "pulse": any(i.get("post", {}).get("author", {}).get("id") == other.pk for i in pulse),
        "livewire": any(i["actor"] and i["actor"]["id"] == other.pk for i in c.get("/api/livewire").json()),
        "profile": c.get(f"/api/members/{other.pk}").status_code == 200,
        "inbox": any(row["other"]["id"] == other.pk for row in c.get("/api/conversations?folder=chats").json()),
        "intros_sent": any(i["target"]["id"] == other.pk for i in c.get("/api/intros?box=sent").json()["items"]),
        "intros_received": any(i["requester"]["id"] == other.pk for i in c.get("/api/intros?box=received").json()["items"]),
        "circuits": any(circ["id"] == w["circuit"].pk for circ in c.get("/api/circuits").json()["items"]),
        "notifications": any(n["actor"] and n["actor"]["id"] == other.pk for n in c.get("/api/notifications").json()["items"]),
    }


def test_before_the_block_the_other_person_shows_up_on_every_surface(world, client_for):
    """Guards the test itself: if a surface were empty here, 'hidden after the block' would prove nothing for it."""
    seen = seen_by(client_for, world["a"], world["b"], world)
    assert all(seen[k] for k in seen if k != "intros_received"), seen  # a sent the intro, so only b has it in "received"
    assert seen_by(client_for, world["b"], world["a"], world)["intros_received"]
    assert all(v for k, v in seen_by(client_for, world["b"], world["a"], world).items() if k != "intros_sent"), "b sees a too"


@pytest.mark.parametrize("blocker", ["a", "b"])
def test_a_block_removes_both_people_from_every_surface(world, client_for, blocker):
    me, other = (world["a"], world["b"]) if blocker == "a" else (world["b"], world["a"])
    assert client_for(me).post(f"/api/members/{other.pk}/block").status_code == 204
    matching.compute_all()  # the nightly run must not bring them back either
    build_all()
    for who, whom in ((me, other), (other, me)):  # BOTH ways: the blocker and the blocked person
        seen = seen_by(client_for, who, whom, world)
        assert not any(seen.values()), f"{who.pk} still sees {whom.pk}: {[k for k, v in seen.items() if v]}"


def test_blocked_people_cannot_reach_each_other_by_any_route(world, client_for):
    a, b = world["a"], world["b"]
    client_for(a).post(f"/api/members/{b.pk}/block")
    for who, whom in ((a, b), (b, a)):
        c = client_for(who)
        assert c.post("/api/conversations", {"member_id": whom.pk, "body": "hi"}).status_code == 404
        assert c.post(f"/api/conversations/{world['conv']}/messages", {"body": "hi"}).status_code == 404
        assert c.post("/api/connections/requests", {"member_id": whom.pk, "note": ""}).status_code == 404
        assert c.post("/api/intros", {"target_id": whom.pk, "message": "hi"}).status_code == 404
        assert c.get(f"/api/members/{whom.pk}/posts").status_code == 404
        assert c.get(f"/api/posts/{world['posts'][whom.pk].pk}").status_code == 404
        assert c.post(f"/api/drop/today/{whom.pk}/swipe", {"direction": "skip"}).status_code == 404


def test_a_block_cleans_up_what_already_existed_between_them(world, client_for):
    a, b, c = world["a"], world["b"], world["c"]
    ConnectionRequest.objects.create(sender=c, recipient=a, note="hi")
    ConnectionRequest.objects.create(sender=a, recipient=b, note="hi again")
    client_for(a).post(f"/api/members/{b.pk}/block")
    assert not Connection.objects.filter(member_a_id=min(a.pk, b.pk), member_b_id=max(a.pk, b.pk)).exists()
    assert not ConnectionRequest.objects.filter(sender=a, recipient=b).exists()
    assert ConnectionRequest.objects.filter(sender=c, recipient=a).exists()  # other people's requests are untouched
    assert Conversation.objects.get(pk=world["conv"]).status == "blocked"
    intro = IntroRequest.objects.get(requester=a, target=b)
    assert (intro.status, intro.stage) == ("expired", "stopped")  # stopped quietly: nobody is told who blocked whom
    circuit = Circuit.objects.get(pk=world["circuit"].pk)
    assert circuit.status == "declined"
    assert Event.objects.filter(
        actor=a, type="member.blocked", target_id=b.pk, payload__intros_ended=1, payload__circuits_ended=1
    ).exists()


def test_the_third_circuit_member_sees_a_plain_decline_and_no_names(world, client_for):
    a, b, c = world["a"], world["b"], world["c"]
    Notification.objects.all().delete()
    client_for(a).post(f"/api/members/{b.pk}/block")
    note = Notification.objects.get(member=c)
    assert note.kind == "circuit.declined" and "actor_id" not in note.payload  # indistinguishable from any other "no"
    assert client_for(c).get(f"/api/circuits/{world['circuit'].pk}").json()["status"] == "declined"
    assert not Notification.objects.filter(
        member=a, kind="circuit.declined"
    ).exists()  # the blocker is not notified of their own act


def test_blocking_is_safe_to_repeat_and_ids_are_not_probeable(world, make_member, client_for):
    a, b = world["a"], world["b"]
    ca = client_for(a)
    assert ca.post(f"/api/members/{b.pk}/block").status_code == 204
    assert ca.post(f"/api/members/{b.pk}/block").status_code == 204
    assert Block.objects.filter(blocker=a, blocked=b).count() == 1
    hidden = make_member("student", profile_visibility="hidden")
    assert ca.post(f"/api/members/{hidden.pk}/block").status_code == 404  # a stranger with a hidden profile looks like no one
    assert ca.post("/api/members/999999/block").status_code == 404
    assert ca.post(f"/api/members/{a.pk}/block").status_code == 422  # not yourself


def test_you_can_block_someone_who_reached_you_even_with_a_hidden_profile(make_member, client_for):
    me, stranger = make_member("student"), make_member("founder", profile_visibility="hidden")
    ConnectionRequest.objects.create(sender=stranger, recipient=me, note="hi")
    assert client_for(me).post(f"/api/members/{stranger.pk}/block").status_code == 204


def test_my_block_list_shows_only_people_i_blocked_never_who_blocked_me(world, client_for):
    a, b, c = world["a"], world["b"], world["c"]
    client_for(a).post(f"/api/members/{b.pk}/block")
    client_for(c).post(f"/api/members/{a.pk}/block")
    mine = client_for(a).get("/api/me/blocks").json()["items"]
    assert [p["id"] for p in mine] == [b.pk]
    assert client_for(b).get("/api/me/blocks").json()["items"] == []
    assert client_for(a).get("/api/me/settings").json()["blocked_count"] == 1


def test_unblocking_restores_visibility_but_not_the_old_connection(world, client_for):
    a, b = world["a"], world["b"]
    client_for(a).post(f"/api/members/{b.pk}/block")
    assert client_for(a).delete(f"/api/members/{b.pk}/block").status_code == 204
    assert client_for(a).get(f"/api/members/{b.pk}").status_code == 200
    assert Conversation.objects.get(pk=world["conv"]).status == "request"  # the chat comes back as a request, not a connection
    assert not Connection.objects.filter(member_a_id=min(a.pk, b.pk), member_b_id=max(a.pk, b.pk)).exists()
    assert client_for(a).delete(f"/api/members/{b.pk}/block").status_code == 404  # nothing left to lift


def test_unblocking_does_not_lift_the_other_persons_block(world, client_for):
    a, b = world["a"], world["b"]
    client_for(a).post(f"/api/members/{b.pk}/block")
    client_for(b).post(f"/api/members/{a.pk}/block")
    client_for(a).delete(f"/api/members/{b.pk}/block")
    assert client_for(a).get(f"/api/members/{b.pk}").status_code == 404  # b still blocks a
    assert Conversation.objects.get(pk=world["conv"]).status == "blocked"


def test_nobody_can_unblock_on_someone_elses_behalf(world, client_for):
    a, b, c = world["a"], world["b"], world["c"]
    client_for(a).post(f"/api/members/{b.pk}/block")
    assert client_for(c).delete(f"/api/members/{b.pk}/block").status_code == 404
    assert client_for(b).delete(f"/api/members/{a.pk}/block").status_code == 404  # the blocked person cannot lift it either
    assert Block.objects.filter(blocker=a, blocked=b).exists()


def test_blocking_from_the_chat_menu_is_the_same_block(world, client_for):
    a, b = world["a"], world["b"]
    assert client_for(a).post(f"/api/conversations/{world['conv']}/block").status_code == 204
    assert Block.objects.filter(blocker=a, blocked=b).exists()
    assert IntroRequest.objects.get(requester=a, target=b).status == "expired"  # cleanup ran, not just the chat flag
    assert Circuit.objects.get(pk=world["circuit"].pk).status == "declined"
    assert Event.objects.filter(actor=a, type="conversation.blocked").exists()


def test_blocking_is_rate_limited(world, make_member, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "block": (2, 3600)}
    a = world["a"]
    others = [make_member("student") for _ in range(3)]
    for o in others:
        ConnectionRequest.objects.create(sender=o, recipient=a, note="hi")
    assert [client_for(a).post(f"/api/members/{o.pk}/block").status_code for o in others] == [204, 204, 429]


def test_the_old_daily_drop_and_matches_stay_clean_after_the_jobs_run_again(world, client_for):
    a, b = world["a"], world["b"]
    client_for(a).post(f"/api/members/{b.pk}/block")
    call_command("compute_matches")
    call_command("build_daily_drops")
    assert (
        not MatchResult.objects.filter(member=a, candidate=b).exists()
        and not MatchResult.objects.filter(member=b, candidate=a).exists()
    )
