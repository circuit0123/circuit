import pytest

from apps.events.models import Event
from apps.messaging import realtime
from apps.messaging.models import Conversation, Message
from apps.notifications.models import Notification
from apps.social.models import MediaUpload

pytestmark = pytest.mark.django_db


def start(client, member, text="Hello!", **kw):
    return client.post("/api/conversations", {"member_id": member.pk, "body": text, **kw})


@pytest.fixture
def broadcasts():
    sent: list[tuple] = []
    realtime.set_sender(lambda topic, event, payload: sent.append((topic, event, payload)))
    return sent


def test_connected_people_chat_directly(make_member, connect, client_for, broadcasts):
    a, b = make_member("student", display_name="Asha"), make_member("founder", display_name="Ben")
    connect(a, b)
    r = start(client_for(a), b)
    assert r.status_code == 201
    conv = r.json()["conversation"]
    assert conv["status"] == "active" and conv["other"]["display_name"] == "Ben" and conv["started_by_me"] is True
    assert r.json()["message"]["mine"] is True and r.json()["message"]["body"] == "Hello!"
    # the other side sees it in Chats with one unread
    chats = client_for(b).get("/api/conversations").json()
    assert [(c["id"], c["unread"], c["other"]["display_name"]) for c in chats] == [(conv["id"], 1, "Asha")]
    assert client_for(b).get("/api/conversations?folder=requests").json() == []


def test_a_stranger_message_is_a_request_that_must_be_accepted(make_member, client_for):
    a, b = make_member("student"), make_member("founder")
    r = start(client_for(a), b, "Can I ask about your startup?")
    cid = r.json()["conversation"]["id"]
    assert r.json()["conversation"]["status"] == "request"
    assert [c["id"] for c in client_for(b).get("/api/conversations?folder=requests").json()] == [cid]
    assert client_for(b).get("/api/conversations").json() == []
    # one message until they answer
    again = client_for(a).post(f"/api/conversations/{cid}/messages", {"body": "Hello? Please reply"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "awaiting_reply"
    accepted = client_for(b).post(f"/api/conversations/{cid}/accept")
    assert accepted.json()["status"] == "active"
    assert client_for(a).post(f"/api/conversations/{cid}/messages", {"body": "Thanks!"}).status_code == 201
    assert client_for(a).post(f"/api/conversations/{cid}/accept").status_code == 404


def test_replying_to_a_request_accepts_it(make_member, client_for):
    a, b = make_member("student"), make_member("founder")
    cid = start(client_for(a), b).json()["conversation"]["id"]
    assert client_for(b).post(f"/api/conversations/{cid}/messages", {"body": "Sure"}).status_code == 201
    assert Conversation.objects.get(pk=cid).status == "active"
    assert Event.objects.filter(type="conversation.accepted").count() == 1


def test_starting_again_continues_the_same_conversation(make_member, connect, client_for):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    first = start(client_for(a), b, "one").json()["conversation"]["id"]
    second = start(client_for(b), a, "two").json()["conversation"]["id"]
    assert first == second and Conversation.objects.count() == 1 and Message.objects.count() == 2
    assert Event.objects.filter(type="conversation.started").count() == 1


def test_messages_are_listed_newest_first_with_a_cursor(make_member, connect, client_for):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    cid = start(client_for(a), b, "m0").json()["conversation"]["id"]
    for i in range(1, 5):
        client_for(b if i % 2 else a).post(f"/api/conversations/{cid}/messages", {"body": f"m{i}"})
    c = client_for(a)
    page1 = c.get(f"/api/conversations/{cid}/messages?limit=2").json()
    assert [m["body"] for m in page1["items"]] == ["m4", "m3"] and [m["mine"] for m in page1["items"]] == [True, False]
    page2 = c.get(f"/api/conversations/{cid}/messages?limit=2&cursor={page1['next_cursor']}").json()
    assert [m["body"] for m in page2["items"]] == ["m2", "m1"]
    page3 = c.get(f"/api/conversations/{cid}/messages?limit=2&cursor={page2['next_cursor']}").json()
    assert [m["body"] for m in page3["items"]] == ["m0"] and page3["next_cursor"] is None


def test_read_marks_only_the_other_persons_messages_and_clears_unread(make_member, connect, client_for):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    cid = start(client_for(a), b, "hi").json()["conversation"]["id"]
    client_for(b).post(f"/api/conversations/{cid}/messages", {"body": "hello"})
    assert client_for(b).post(f"/api/conversations/{cid}/read").json() == {"marked": 1}
    assert client_for(b).get("/api/conversations").json()[0]["unread"] == 0
    assert client_for(a).get("/api/conversations").json()[0]["unread"] == 1
    sent = client_for(a).get(f"/api/conversations/{cid}/messages").json()["items"]
    assert all(m["read_at"] is None for m in sent)  # read receipts are off (see test_b7_messaging for the on case)


def test_blocking_ends_the_conversation_and_blocks_everything_else(make_member, connect, client_for, make_post):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    cid = start(client_for(a), b).json()["conversation"]["id"]
    assert client_for(b).post(f"/api/conversations/{cid}/block").status_code == 204
    assert start(client_for(a), b).status_code == 404  # cannot start a new one either
    assert client_for(a).get(f"/api/posts/{make_post(b, 'everyone').pk}").status_code == 404
    assert Event.objects.filter(type="conversation.blocked").count() == 1


def test_validation_empty_long_self_and_unknown(make_member, connect, client_for):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    c = client_for(a)
    assert start(c, b, "").status_code == 422
    assert start(c, b, "   ").status_code == 422
    assert start(c, b, "x" * 2001).status_code == 422
    assert start(c, a).status_code == 422
    assert c.post("/api/conversations", {"member_id": 999999, "body": "hi"}).status_code == 404


def test_a_hidden_profile_can_only_be_reached_by_connections_or_org(make_member, make_org, connect, client_for):
    org = make_org()
    hidden = make_member("mentor", profile_visibility="hidden", org=org)
    stranger, mate, friend = make_member("student"), make_member("student", org=org), make_member("founder")
    connect(hidden, friend)
    assert start(client_for(stranger), hidden).status_code == 404
    assert start(client_for(mate), hidden).status_code == 201
    assert start(client_for(friend), hidden).status_code == 201


def test_one_unread_notification_per_conversation(make_member, connect, client_for):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    cid = start(client_for(a), b, "1").json()["conversation"]["id"]
    for t in "23":
        client_for(a).post(f"/api/conversations/{cid}/messages", {"body": t})
    notes = Notification.objects.filter(member=b, kind="message.new")
    assert notes.count() == 1 and notes[0].payload == {"conversation_id": cid, "actor_id": a.pk}
    client_for(b).post(f"/api/conversations/{cid}/read")
    assert Notification.objects.get(member=b).read_at is not None
    client_for(a).post(f"/api/conversations/{cid}/messages", {"body": "4"})
    assert Notification.objects.filter(member=b, kind="message.new").count() == 2
    assert not Notification.objects.filter(member=a).exists()


def test_rate_limits(make_member, connect, client_for, settings):
    a, b, c3 = make_member("student"), make_member("founder"), make_member("mentor")
    connect(a, b)
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "message": (2, 60), "conversation_start": (1, 60)}
    cid = start(client_for(a), b).json()["conversation"]["id"]
    assert client_for(a).post(f"/api/conversations/{cid}/messages", {"body": "2"}).status_code == 201
    assert client_for(a).post(f"/api/conversations/{cid}/messages", {"body": "3"}).status_code == 429
    assert start(client_for(c3), a).status_code == 201
    assert start(client_for(c3), b).status_code == 429


# -- images ------------------------------------------------------------------------------------------
def test_a_message_can_carry_an_image(make_member, connect, client_for):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    up = MediaUpload.objects.create(owner=a, purpose="message", path=f"message/{a.pk}/img", status="ready", width=20, height=10)
    r = start(client_for(a), b, "", upload_id=up.pk)
    assert r.status_code == 201
    img = r.json()["message"]["image"]
    assert img["w480"].startswith("https://storage.test/read/messages/") and (img["width"], img["height"]) == (20, 10)
    seen = client_for(b).get(f"/api/conversations/{r.json()['conversation']['id']}/messages").json()["items"][0]
    assert seen["image"]["w1440"].endswith("w1440.webp?token=t")
    assert start(client_for(a), b, "", upload_id=up.pk).status_code == 404  # an image is sent once


# -- realtime ----------------------------------------------------------------------------------------
def test_each_message_broadcasts_ids_only_to_the_conversation_channel(
    make_member, connect, client_for, broadcasts, django_capture_on_commit_callbacks
):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    with django_capture_on_commit_callbacks(execute=True):  # Broadcasts go out after the commit, never before
        r = start(client_for(a), b, "a secret plan")
    cid, mid = r.json()["conversation"]["id"], r.json()["message"]["id"]
    chat = [e for e in broadcasts if e[0].startswith("conversation:")]
    assert chat == [(f"conversation:{cid}", "message", {"message_id": mid, "conversation_id": cid})]
    nudges = [e for e in broadcasts if e[0].startswith("member:")]  # and b's notification channel hears a notification id
    assert sorted((t, ev, list(p)) for t, ev, p in nudges) == [  # a notification id, and "a new conversation" (ids only)
        (f"member:{b.pk}", "conversation", ["conversation_id"]),
        (f"member:{b.pk}", "notification", ["notification_id"]),
    ]
    assert "secret" not in str(broadcasts)


def test_a_failing_broadcast_does_not_lose_the_message(make_member, connect, client_for, django_capture_on_commit_callbacks):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)

    def boom(*args):
        raise RuntimeError("realtime is down")

    realtime.set_sender(boom)
    with django_capture_on_commit_callbacks(execute=True):
        assert start(client_for(a), b).status_code == 201
    assert Message.objects.count() == 1


def test_a_message_that_was_refused_does_not_broadcast(make_member, client_for, broadcasts, django_capture_on_commit_callbacks):
    a, b = make_member("student"), make_member("founder")
    with django_capture_on_commit_callbacks(execute=True):
        cid = start(client_for(a), b).json()["conversation"]["id"]
    broadcasts.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert client_for(a).post(f"/api/conversations/{cid}/messages", {"body": "again"}).status_code == 409
    assert broadcasts == []


def test_supabase_sender_posts_to_the_realtime_api_with_a_private_topic(settings, monkeypatch):
    settings.SUPABASE_URL = "https://x.supabase.co"
    settings.SUPABASE_SERVICE_ROLE_KEY = "service-key"
    calls = []

    class R:
        status_code = 202

    monkeypatch.setattr(realtime.httpx, "post", lambda url, **kw: calls.append((url, kw)) or R())
    realtime.set_sender(None)
    realtime.broadcast(7, 99)
    url, kw = calls[0]
    assert url == "https://x.supabase.co/realtime/v1/api/broadcast" and kw["timeout"] == 3.0
    assert kw["json"]["messages"] == [
        {"topic": "conversation:7", "event": "message", "payload": {"message_id": 99, "conversation_id": 7}, "private": True}
    ]


# -- Postgres side of the private channel ---------------------------------------------------------------
def test_the_channel_membership_function_lets_in_exactly_the_two_people(make_member, connect, client_for):
    from django.db import connection

    a, b, outsider = make_member("student"), make_member("founder"), make_member("mentor")
    connect(a, b)
    cid = start(client_for(a), b).json()["conversation"]["id"]

    def allowed(member):
        with connection.cursor() as cur:
            cur.execute("SELECT public.is_conversation_member(%s, %s)", [cid, member.auth_user_id])
            return cur.fetchone()[0]

    assert allowed(a) and allowed(b) and not allowed(outsider)
    client_for(b).post(f"/api/conversations/{cid}/block")
    assert not allowed(a) and not allowed(b)  # a blocked conversation closes its channel
