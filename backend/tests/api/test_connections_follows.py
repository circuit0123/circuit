import pytest

from apps.accounts.models import Connection, ConnectionRequest
from apps.events.models import Event
from apps.social.models import Follow

pytestmark = pytest.mark.django_db


def ask(client, member, note="Met you at the hackathon"):
    return client.post("/api/connections/requests", {"member_id": member.pk, "note": note})


def test_ask_accept_and_become_connections(make_member, client_for):
    a, b = make_member("student", display_name="Asha"), make_member("founder", display_name="Ben")
    r = ask(client_for(a), b)
    assert r.status_code == 201 and r.json()["note"] == "Met you at the hackathon" and r.json()["status"] == "pending"
    incoming = client_for(b).get("/api/connections/requests").json()
    assert [(x["id"], x["sender"]["display_name"]) for x in incoming] == [(r.json()["id"], "Asha")]
    done = client_for(b).post(f"/api/connections/requests/{r.json()['id']}/respond", {"accept": True})
    assert done.status_code == 200 and done.json()["status"] == "accepted"
    assert Connection.objects.count() == 1
    assert [p["id"] for p in client_for(a).get("/api/connections").json()] == [b.pk]
    assert [p["id"] for p in client_for(b).get("/api/connections").json()] == [a.pk]
    assert client_for(b).get("/api/connections/requests").json() == []
    assert Event.objects.filter(type__in=["connection.requested", "connection.responded"]).count() == 2


def test_declining_does_not_connect_and_blocks_asking_again_for_a_while(make_member, client_for):
    a, b = make_member("student"), make_member("founder")
    rid = ask(client_for(a), b).json()["id"]
    assert client_for(b).post(f"/api/connections/requests/{rid}/respond", {"accept": False}).json()["status"] == "declined"
    assert not Connection.objects.exists()
    again = ask(client_for(a), b)
    assert again.status_code == 409 and again.json()["error"]["code"] == "recently_declined"


def test_asking_twice_or_when_connected_is_a_409(make_member, connect, client_for):
    a, b, c = make_member("student"), make_member("founder"), make_member("mentor")
    assert ask(client_for(a), b).status_code == 201
    assert ask(client_for(a), b).json()["error"]["code"] == "already_requested"
    connect(a, c)
    assert ask(client_for(a), c).json()["error"]["code"] == "already_connected"


def test_asking_someone_who_already_asked_you_connects_you(make_member, client_for):
    a, b = make_member("student"), make_member("founder")
    ask(client_for(a), b)
    r = ask(client_for(b), a)
    assert r.status_code == 201 and r.json()["status"] == "accepted" and Connection.objects.count() == 1
    assert ConnectionRequest.objects.count() == 1


def test_a_request_to_yourself_blocked_hidden_or_suspended_people(make_member, block, client_for):
    from django.utils import timezone

    a, b, hidden, gone = (
        make_member("student"),
        make_member("founder"),
        make_member("mentor", profile_visibility="hidden"),
        make_member("mentor"),
    )
    gone.suspended_at = timezone.now()
    gone.save()
    block(b, a)
    c = client_for(a)
    assert ask(c, a).status_code == 422
    assert ask(c, b).status_code == 404  # blocked me
    assert ask(c, hidden).status_code == 404
    assert ask(c, gone).status_code == 404
    assert ask(c, make_member("partner_admin")).status_code == 404  # staff are not in the network


def test_note_limit_and_rate_limit(make_member, client_for, settings):
    a, b, c3 = make_member("student"), make_member("founder"), make_member("mentor")
    assert ask(client_for(a), b, "x" * 301).status_code == 422
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "connection_request": (1, 60)}
    assert ask(client_for(a), b).status_code == 201
    assert ask(client_for(a), c3).status_code == 429


def test_answering_twice_is_a_409(make_member, client_for):
    a, b = make_member("student"), make_member("founder")
    rid = ask(client_for(a), b).json()["id"]
    client_for(b).post(f"/api/connections/requests/{rid}/respond", {"accept": True})
    assert client_for(b).post(f"/api/connections/requests/{rid}/respond", {"accept": False}).status_code == 409


def test_removing_a_connection(make_member, connect, client_for):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    assert client_for(a).delete(f"/api/connections/{b.pk}").status_code == 204
    assert client_for(a).delete(f"/api/connections/{b.pk}").status_code == 404
    assert Event.objects.filter(type="connection.removed").count() == 1


def test_blocked_people_vanish_from_my_connection_list(make_member, connect, block, client_for):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    block(a, b)
    assert client_for(a).get("/api/connections").json() == []


# -- follows ------------------------------------------------------------------------------------------
def test_follow_unfollow_are_safe_to_repeat_and_private(make_member, make_startup, client_for):
    me, other = make_member("student"), make_member("student")
    s = make_startup("Acme", "acme.io", hiring=True, sector="fintech")
    c = client_for(me)
    assert c.post(f"/api/startups/{s.pk}/follow").status_code == 204
    assert c.post(f"/api/startups/{s.pk}/follow").status_code == 204
    assert Follow.objects.count() == 1 and Event.objects.filter(type="follow.added").count() == 1
    assert c.get("/api/me/follows").json() == [{"id": s.pk, "name": "Acme", "sector": "fintech", "hiring": True}]
    assert client_for(other).get("/api/me/follows").json() == []
    assert c.delete(f"/api/startups/{s.pk}/follow").status_code == 204
    assert c.delete(f"/api/startups/{s.pk}/follow").status_code == 204
    assert not Follow.objects.exists() and Event.objects.filter(type="follow.removed").count() == 1


def test_following_an_unknown_startup_is_a_404(make_member, client_for):
    assert client_for(make_member()).post("/api/startups/999999/follow").status_code == 404
