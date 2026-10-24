from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Connection
from apps.events.models import Event
from apps.intros.models import IntroRequest
from apps.moderation.models import Block
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


def connect(x, y, strength=0.9):
    Connection.objects.create(member_a_id=min(x.pk, y.pk), member_b_id=max(x.pk, y.pk), strength=strength)


@pytest.fixture
def trio(make_member):
    """Sneha asks Vikram through Lakshmi: asker - broker - target, no direct link."""
    asker, broker, target = make_member("founder"), make_member("mentor"), make_member("investor")
    connect(asker, broker)
    connect(broker, target)
    return asker, broker, target


def ask(client, target, message="Could you introduce us?"):
    return client.post("/api/intros", {"target_id": target.pk, "message": message})


def kinds(member):
    return list(Notification.objects.filter(member=member).order_by("id").values_list("kind", flat=True))


# -- the path -----------------------------------------------------------------------------------
def test_preview_shows_who_would_vouch(trio, client_for):
    asker, broker, target = trio
    body = client_for(asker).get(f"/api/intros/path/{target.pk}").json()
    assert body["via"]["id"] == broker.pk and body["target"]["id"] == target.pk


def test_preview_for_someone_already_connected_has_no_broker(trio, client_for):
    asker, broker, _ = trio
    assert client_for(asker).get(f"/api/intros/path/{broker.pk}").json()["via"] is None


def test_no_path_self_hidden_and_unknown_people(trio, make_member, client_for):
    asker, _, _ = trio
    c = client_for(asker)
    stranger = make_member("mentor")
    r = c.get(f"/api/intros/path/{stranger.pk}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_warm_path"
    assert c.get(f"/api/intros/path/{asker.pk}").status_code == 422
    assert c.get("/api/intros/path/999999").status_code == 404
    hidden = make_member("investor", profile_visibility="hidden")
    connect(asker, hidden)
    assert c.get(f"/api/intros/path/{hidden.pk}").status_code == 404


def test_a_blocked_or_suspended_broker_breaks_the_path(trio, client_for):
    asker, broker, target = trio
    Block.objects.create(blocker=target, blocked=broker)
    assert client_for(asker).get(f"/api/intros/path/{target.pk}").status_code == 404
    Block.objects.all().delete()
    broker.suspended_at = timezone.now()
    broker.save()
    assert client_for(asker).get(f"/api/intros/path/{target.pk}").status_code == 404


# -- the request ---------------------------------------------------------------------------------
def test_request_goes_to_the_broker_first(trio, client_for):
    asker, broker, target = trio
    r = ask(client_for(asker), target)
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["stage"] == "broker" and body["status"] == "pending" and body["my_role"] == "requester"
    assert body["via"]["id"] == broker.pk and body["can_respond"] is False
    assert kinds(broker) == ["intro.broker_request"] and kinds(target) == []  # the target hears nothing yet
    assert Event.objects.filter(type="intro.requested", actor_id=asker.pk).count() == 1


def test_asking_again_while_open_returns_the_same_request(trio, client_for):
    asker, _, target = trio
    c = client_for(asker)
    first, again = ask(c, target), ask(c, target)
    assert (first.status_code, again.status_code) == (201, 200) and first.json()["id"] == again.json()["id"]
    assert IntroRequest.objects.count() == 1


def test_a_direct_connection_skips_the_broker(trio, client_for):
    asker, broker, _ = trio
    body = ask(client_for(asker), broker).json()
    assert body["stage"] == "target" and body["via"] is None
    assert kinds(broker) == ["intro.received"]


def test_minors_cannot_request_intros(trio, make_member, client_for):
    _, broker, target = trio
    minor = make_member("student", is_minor=True)
    connect(minor, broker)
    assert ask(client_for(minor), target).status_code == 403


# -- the full flow --------------------------------------------------------------------------------
def test_broker_then_target_then_rating(trio, client_for):
    asker, broker, target = trio
    intro_id = ask(client_for(asker), target).json()["id"]
    bc, tc, ac = client_for(broker), client_for(target), client_for(asker)

    assert bc.get("/api/intros?box=brokered").json()["items"][0]["can_respond"] is True
    assert tc.get("/api/intros?box=received").json()["items"] == []  # not vouched for yet
    r = bc.post(f"/api/intros/{intro_id}/respond", {"accept": True}).json()
    assert r["stage"] == "target" and r["status"] == "pending" and r["my_role"] == "broker"
    assert kinds(asker) == ["intro.vouched"] and kinds(target) == ["intro.received"]

    assert ac.post(f"/api/intros/{intro_id}/rating", {"rating": 4}).status_code == 409  # not accepted yet
    inbox = tc.get("/api/intros?box=received").json()["items"]
    assert inbox[0]["id"] == intro_id and inbox[0]["can_respond"] is True and inbox[0]["my_role"] == "target"
    done = tc.post(f"/api/intros/{intro_id}/respond", {"accept": True}).json()
    assert done["status"] == "accepted" and done["stage"] == "done"
    assert kinds(asker)[-1] == "intro.accepted" and kinds(broker)[-1] == "intro.accepted"

    rated = ac.post(f"/api/intros/{intro_id}/rating", {"rating": 5}).json()
    assert rated["status"] == "completed" and rated["outcome_rating"] == 5
    assert ac.post(f"/api/intros/{intro_id}/rating", {"rating": 1}).json()["outcome_rating"] == 5  # safe to repeat
    assert set(Event.objects.filter(type__startswith="intro.").values_list("type", flat=True)) == {
        "intro.requested", "intro.broker_responded", "intro.responded", "intro.rated",
    }  # fmt: skip


def test_broker_declines_and_the_target_never_sees_it(trio, client_for):
    asker, broker, target = trio
    intro_id = ask(client_for(asker), target).json()["id"]
    r = client_for(broker).post(f"/api/intros/{intro_id}/respond", {"accept": False}).json()
    assert r["status"] == "declined" and r["stage"] == "stopped"
    assert kinds(asker) == ["intro.declined"] and kinds(target) == []
    assert client_for(target).get("/api/intros?box=received").json()["items"] == []


def test_target_declines(trio, client_for):
    asker, broker, target = trio
    intro_id = ask(client_for(asker), target).json()["id"]
    client_for(broker).post(f"/api/intros/{intro_id}/respond", {"accept": True})
    r = client_for(target).post(f"/api/intros/{intro_id}/respond", {"accept": False}).json()
    assert r["status"] == "declined" and kinds(broker)[-1] == "intro.declined"
    assert client_for(asker).post(f"/api/intros/{intro_id}/rating", {"rating": 3}).status_code == 409


def test_turn_rules_and_privacy_of_ids(trio, make_member, client_for):
    asker, broker, target = trio
    intro_id = ask(client_for(asker), target).json()["id"]
    url = f"/api/intros/{intro_id}/respond"
    assert client_for(target).post(url, {"accept": True}).status_code == 409  # the broker goes first
    assert client_for(asker).post(url, {"accept": True}).status_code == 409  # you cannot approve your own request
    assert client_for(make_member("founder")).post(url, {"accept": True}).status_code == 404
    assert client_for(make_member("founder")).post(f"/api/intros/{intro_id}/rating", {"rating": 3}).status_code == 404
    client_for(broker).post(url, {"accept": True})
    again = client_for(broker).post(url, {"accept": False})  # a repeated answer changes nothing
    assert again.status_code == 200 and again.json()["stage"] == "target"
    assert client_for(asker).post(f"/api/intros/{intro_id}/rating", {"rating": 6}).status_code == 422


def test_notifications_carry_ids_only(trio, client_for):
    asker, broker, target = trio
    ask(client_for(asker), target, message="Secret pitch about my startup")
    assert Notification.objects.get(member=broker).payload == {
        "intro_id": IntroRequest.objects.get().pk,
        "actor_id": asker.pk,
    }  # ids only


# -- limits ---------------------------------------------------------------------------------------
def test_weekly_limit_on_requests_sent(trio, make_member, client_for, settings):
    settings.INTRO_WEEKLY_LIMIT = 1
    asker, broker, target = trio
    other = make_member("investor")
    connect(broker, other)
    c = client_for(asker)
    assert ask(c, target).status_code == 201
    r = ask(c, other)
    assert r.status_code == 409 and r.json()["error"]["code"] == "intro_weekly_limit"
    IntroRequest.objects.update(created_at=timezone.now() - timedelta(days=8))
    assert ask(c, other).status_code == 201


def test_target_capacity_is_open_intro_slots(trio, make_member, client_for):
    asker, broker, target = trio
    target.open_intro_slots = 1
    target.save()
    other = make_member("founder")
    connect(other, broker)
    assert ask(client_for(other), target).status_code == 201
    r = ask(client_for(asker), target)
    assert r.status_code == 409 and r.json()["error"]["code"] == "target_full"


def test_rate_limit(trio, make_member, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "intro": (1, 86400)}
    settings.INTRO_WEEKLY_LIMIT = 10
    asker, broker, target = trio
    other = make_member("investor")
    connect(broker, other)
    c = client_for(asker)
    assert ask(c, target).status_code == 201
    assert ask(c, target).status_code == 200  # repeating an open request is free
    assert ask(c, other).status_code == 429


# -- expiry ----------------------------------------------------------------------------------------
def test_expired_requests_read_as_expired_and_cannot_be_answered(trio, client_for):
    asker, broker, target = trio
    intro_id = ask(client_for(asker), target).json()["id"]
    IntroRequest.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    assert client_for(asker).get("/api/intros").json()["items"][0]["status"] == "expired"
    r = client_for(broker).post(f"/api/intros/{intro_id}/respond", {"accept": True})
    assert r.status_code == 409 and r.json()["error"]["code"] == "intro_expired"
    assert IntroRequest.objects.get().status == "expired"


def test_expire_items_marks_and_notifies_once(trio, client_for, capsys):
    asker, _, target = trio
    ask(client_for(asker), target)
    IntroRequest.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    call_command("expire_items")
    call_command("expire_items")
    out = capsys.readouterr().out
    assert "introductions expired: 1" in out and "introductions expired: 0" in out
    assert IntroRequest.objects.get().stage == "stopped" and kinds(asker) == ["intro.expired"]


def test_list_pagination_and_bad_box(trio, client_for):
    asker, _, target = trio
    ask(client_for(asker), target)
    c = client_for(asker)
    assert c.get("/api/intros?limit=1").json()["count"] == 1
    assert c.get("/api/intros?box=everything").status_code == 422
