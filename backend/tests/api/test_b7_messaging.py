"""B7 part 1: decline a request, unread counts, new-conversation Realtime event, read receipts, typed message image."""

import pytest

from apps.events.models import Event
from apps.messaging import realtime
from apps.messaging.models import Conversation

pytestmark = pytest.mark.django_db


def start(client, member, text="Hello!", **kw):
    return client.post("/api/conversations", {"member_id": member.pk, "body": text, **kw})


@pytest.fixture
def broadcasts():
    sent: list[tuple] = []
    realtime.set_sender(lambda topic, event, payload: sent.append((topic, event, payload)))
    return sent


@pytest.fixture
def stranger_request(make_member, client_for):
    """a (the sender) has sent a request to b (the recipient), who are not connected. Open to strangers is the default."""
    a, b = make_member("founder"), make_member("student")
    r = start(client_for(a), b)
    assert r.status_code == 201 and r.json()["conversation"]["status"] == "request"
    return a, b, r.json()["conversation"]["id"]


# -- decline -------------------------------------------------------------------------------------------
def test_declining_a_request_removes_it_for_me_and_not_for_them(stranger_request, client_for):
    a, b, cid = stranger_request
    assert client_for(b).post(f"/api/conversations/{cid}/decline").status_code == 204
    assert client_for(b).get("/api/conversations?folder=requests").json() == []
    assert client_for(b).get(f"/api/conversations/{cid}").status_code == 404
    mine = (
        client_for(a).get("/api/conversations?folder=chats").json()
        + client_for(a).get("/api/conversations?folder=requests").json()
    )
    assert [c["status"] for c in mine] == ["request"]  # the sender is not told: it looks like an unanswered request
    assert Event.objects.filter(type="conversation.declined", actor=b).exists()


def test_the_sender_still_cannot_pile_on_after_a_decline(stranger_request, client_for):
    a, b, cid = stranger_request
    client_for(b).post(f"/api/conversations/{cid}/decline")
    r = client_for(a).post(f"/api/conversations/{cid}/messages", {"body": "hello?"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "awaiting_reply"


def test_a_declined_request_sends_the_sender_no_notice(stranger_request, client_for):
    a, b, cid = stranger_request
    from apps.notifications.models import Notification

    before = Notification.objects.filter(member=a).count()
    client_for(b).post(f"/api/conversations/{cid}/decline")
    assert Notification.objects.filter(member=a).count() == before


def test_only_the_recipient_can_decline(stranger_request, make_member, client_for):
    a, b, cid = stranger_request
    assert client_for(a).post(f"/api/conversations/{cid}/decline").status_code == 404  # not your own request
    assert client_for(make_member("student")).post(f"/api/conversations/{cid}/decline").status_code == 404  # IDOR
    assert Conversation.objects.get(pk=cid).declined_by_id is None


def test_a_chat_cannot_be_declined(make_member, connect, client_for):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    cid = start(client_for(a), b).json()["conversation"]["id"]
    r = client_for(b).post(f"/api/conversations/{cid}/decline")
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_a_request"


def test_declining_twice_is_a_404_the_second_time(stranger_request, client_for):
    a, b, cid = stranger_request
    client_for(b).post(f"/api/conversations/{cid}/decline")
    assert client_for(b).post(f"/api/conversations/{cid}/decline").status_code == 404


def test_writing_back_after_declining_accepts_it_after_all(stranger_request, client_for):
    a, b, cid = stranger_request
    client_for(b).post(f"/api/conversations/{cid}/decline")
    r = start(client_for(b), a, "actually, hi")
    assert r.status_code == 201 and r.json()["conversation"]["status"] == "active"
    assert Conversation.objects.get(pk=cid).declined_by_id is None


# -- unread counts -----------------------------------------------------------------------------------------
def test_unread_counts_per_folder_and_cleared_by_reading(stranger_request, make_member, connect, client_for):
    a, b, cid = stranger_request
    friend = make_member("founder")
    connect(b, friend)
    start(client_for(friend), b, "yo")
    assert client_for(b).get("/api/conversations/unread-count").json() == {"chats": 1, "requests": 1}
    client_for(b).post(f"/api/conversations/{cid}/read")
    assert client_for(b).get("/api/conversations/unread-count").json() == {"chats": 1, "requests": 0}
    assert client_for(a).get("/api/conversations/unread-count").json() == {
        "chats": 0,
        "requests": 0,
    }  # my own message is not unread


def test_a_declined_request_is_not_counted(stranger_request, client_for):
    a, b, cid = stranger_request
    client_for(b).post(f"/api/conversations/{cid}/decline")
    assert client_for(b).get("/api/conversations/unread-count").json() == {"chats": 0, "requests": 0}


def test_blocked_people_are_not_counted(stranger_request, block, client_for):
    a, b, cid = stranger_request
    block(b, a)
    assert client_for(b).get("/api/conversations/unread-count").json() == {"chats": 0, "requests": 0}


def test_unread_requests_are_always_zero_for_under_18s(make_member, make_org, client_for):
    org = make_org()
    kid = make_member("student", org=org, is_minor=True)
    staff = make_member("partner_admin", org=org)
    start(client_for(staff), kid, "welcome")
    assert client_for(kid).get("/api/conversations/unread-count").json()["requests"] == 0


def test_unread_count_needs_sign_in(client):
    assert client.get("/api/conversations/unread-count").status_code == 401


# -- Realtime: new conversations -----------------------------------------------------------------------------
def test_a_new_conversation_nudges_the_recipients_member_channel(
    make_member, client_for, broadcasts, django_capture_on_commit_callbacks
):
    a, b = make_member("founder"), make_member("student")
    with django_capture_on_commit_callbacks(execute=True):
        cid = start(client_for(a), b).json()["conversation"]["id"]
    assert (f"member:{b.pk}", "conversation", {"conversation_id": cid}) in broadcasts
    assert not [e for e in broadcasts if e[0] == f"member:{a.pk}" and e[1] == "conversation"]  # the sender is not nudged


def test_accepting_nudges_the_person_who_asked(stranger_request, client_for, broadcasts, django_capture_on_commit_callbacks):
    a, b, cid = stranger_request
    broadcasts.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert client_for(b).post(f"/api/conversations/{cid}/accept").status_code == 200
    assert (f"member:{a.pk}", "conversation", {"conversation_id": cid}) in broadcasts


def test_replying_to_a_request_also_nudges_the_person_who_asked(
    stranger_request, client_for, broadcasts, django_capture_on_commit_callbacks
):
    a, b, cid = stranger_request
    broadcasts.clear()
    with django_capture_on_commit_callbacks(execute=True):
        client_for(b).post(f"/api/conversations/{cid}/messages", {"body": "hi back"})
    assert (f"member:{a.pk}", "conversation", {"conversation_id": cid}) in broadcasts


# -- read receipts ----------------------------------------------------------------------------------------
def make_pair(make_member, connect, client_for, a_on, b_on):
    a, b = make_member("student", read_receipts=a_on), make_member("founder", read_receipts=b_on)
    connect(a, b)
    cid = start(client_for(a), b, "hi").json()["conversation"]["id"]
    client_for(b).post(f"/api/conversations/{cid}/read")
    return a, b, cid


def test_read_receipts_show_only_when_both_have_them_on(make_member, connect, client_for):
    a, b, cid = make_pair(make_member, connect, client_for, True, True)
    mine = client_for(a).get(f"/api/conversations/{cid}/messages").json()["items"]
    assert mine[0]["read_at"] is not None
    assert client_for(a).get("/api/conversations").json()[0]["last_message"]["read_at"] is not None


@pytest.mark.parametrize("a_on,b_on", [(True, False), (False, True), (False, False)])
def test_read_receipts_are_hidden_unless_both_are_on(make_member, connect, client_for, a_on, b_on):
    a, b, cid = make_pair(make_member, connect, client_for, a_on, b_on)
    assert client_for(a).get(f"/api/conversations/{cid}/messages").json()["items"][0]["read_at"] is None
    last = client_for(a).get("/api/conversations").json()[0]["last_message"]
    assert last["read_at"] is None


def test_the_other_persons_messages_never_carry_read_at(make_member, connect, client_for):
    a, b, cid = make_pair(make_member, connect, client_for, True, True)
    client_for(b).post(f"/api/conversations/{cid}/messages", {"body": "reply"})
    items = client_for(a).get(f"/api/conversations/{cid}/messages").json()["items"]
    assert [m["read_at"] is None for m in items if not m["mine"]] == [True]


# -- message image is a typed object -----------------------------------------------------------------------
def test_a_message_image_has_the_documented_shape(make_member, connect, client_for, make_image):
    from apps.social.models import MediaUpload
    from core.storage import get_storage

    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    c = client_for(a)
    r = c.post("/api/media/uploads", {"purpose": "message", "content_type": "image/png", "size": 100})
    up = MediaUpload.objects.get(pk=r.json()["id"])
    get_storage().put("messages", f"{up.path}/original", make_image("PNG", (800, 600)), "image/png")
    c.post(f"/api/media/uploads/{up.pk}/complete")
    image = start(c, b, "", upload_id=up.pk).json()["message"]["image"]
    assert set(image) == {"width", "height", "w1440", "w480"} and (image["width"], image["height"]) == (800, 600)


def test_every_message_nudges_only_the_other_persons_member_channel(
    make_member, connect, client_for, broadcasts, django_capture_on_commit_callbacks
):
    a, b = make_member("student"), make_member("founder")
    connect(a, b)
    cid = start(client_for(a), b).json()["conversation"]["id"]
    broadcasts.clear()
    with django_capture_on_commit_callbacks(execute=True):
        client_for(b).post(f"/api/conversations/{cid}/messages", {"body": "second"})
    nudges = [e for e in broadcasts if e[1] == "conversation"]
    assert nudges == [(f"member:{a.pk}", "conversation", {"conversation_id": cid})]
