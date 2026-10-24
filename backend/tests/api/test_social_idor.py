"""IDOR: every id in a URL or body belongs to someone; asking with another member's id must look like "not found"."""

import pytest

from apps.accounts.models import ConnectionRequest
from apps.messaging.models import Conversation, Message
from apps.social.models import MediaUpload, Post, PostMedia, Reaction, Reply

pytestmark = pytest.mark.django_db


@pytest.fixture
def pair(make_member, connect):
    owner, intruder = make_member("student", display_name="Owner"), make_member("student", display_name="Intruder")
    return owner, intruder


def ready_upload(owner, purpose="post", name="abc"):
    return MediaUpload.objects.create(
        owner=owner, purpose=purpose, path=f"{purpose}/{owner.pk}/{name}", status="ready", width=10, height=10
    )


# -- posts and replies --------------------------------------------------------------------------------
def test_only_the_author_can_delete_a_post(pair, make_post, client_for):
    owner, intruder = pair
    post = make_post(owner, "everyone")
    r = client_for(intruder).delete(f"/api/posts/{post.pk}")
    assert r.status_code == 404 and Post.objects.filter(pk=post.pk).exists()
    assert client_for(owner).delete(f"/api/posts/{post.pk}").status_code == 204
    assert not Post.objects.filter(pk=post.pk).exists()


def test_a_post_i_cannot_see_cannot_be_reacted_to_or_replied_to(pair, make_post, client_for):
    owner, intruder = pair
    post = make_post(owner, "connections")  # the intruder is not a connection
    c = client_for(intruder)
    assert c.put(f"/api/posts/{post.pk}/reactions/helpful").status_code == 404
    assert c.post(f"/api/posts/{post.pk}/replies", {"body": "hi"}).status_code == 404
    assert c.get(f"/api/posts/{post.pk}/replies").status_code == 404
    assert not Reaction.objects.exists() and not Reply.objects.exists()


def test_deleting_someone_elses_reply_is_a_404_but_the_post_author_may_moderate_their_thread(
    pair, make_post, make_member, client_for
):
    owner, intruder = pair
    third = make_member("founder")
    post = make_post(owner, "everyone")
    reply = Reply.objects.create(post=post, author=intruder, body="Nice")
    assert client_for(third).delete(f"/api/replies/{reply.pk}").status_code == 404
    assert Reply.objects.filter(pk=reply.pk).exists()
    assert client_for(owner).delete(f"/api/replies/{reply.pk}").status_code == 204  # on their own post


def test_a_reply_cannot_hang_off_a_parent_from_another_post(pair, make_post, client_for):
    owner, intruder = pair
    mine, other = make_post(owner, "everyone"), make_post(owner, "everyone")
    parent = Reply.objects.create(post=other, author=owner, body="elsewhere")
    r = client_for(intruder).post(f"/api/posts/{mine.pk}/replies", {"body": "x", "parent_id": parent.pk})
    assert r.status_code == 404


def test_unreacting_only_touches_my_own_reaction(pair, make_post, client_for):
    owner, intruder = pair
    post = make_post(owner, "everyone")
    Reaction.objects.create(post=post, member=owner, kind="helpful")
    assert client_for(intruder).delete(f"/api/posts/{post.pk}/reactions/helpful").status_code == 204
    assert Reaction.objects.filter(member=owner).count() == 1


# -- uploads -----------------------------------------------------------------------------------------
def test_someone_elses_upload_cannot_be_completed_or_attached(pair, client_for):
    owner, intruder = pair
    up = ready_upload(owner)
    c = client_for(intruder)
    assert c.post(f"/api/media/uploads/{up.pk}/complete").status_code == 404
    r = c.post("/api/posts", {"body": "mine now", "visibility": "everyone", "media": [{"upload_id": up.pk, "alt_text": "x"}]})
    assert r.status_code == 404 and not Post.objects.exists()


def test_an_upload_can_be_attached_once_and_only_for_its_purpose(pair, client_for):
    owner, _ = pair
    up, chat = ready_upload(owner), ready_upload(owner, "message", "chat")
    c = client_for(owner)
    body = {"body": "", "visibility": "everyone", "media": [{"upload_id": up.pk, "alt_text": "screen"}]}
    assert c.post("/api/posts", body).status_code == 201
    assert c.post("/api/posts", body).status_code == 404  # already used
    wrong = {"body": "", "visibility": "everyone", "media": [{"upload_id": chat.pk, "alt_text": "x"}]}
    assert c.post("/api/posts", wrong).status_code == 404  # a chat image is not a build-log image
    assert PostMedia.objects.count() == 1


def test_a_message_cannot_carry_someone_elses_image(pair, connect, client_for):
    owner, intruder = pair
    connect(owner, intruder)
    stolen = ready_upload(owner, "message", "chat")
    r = client_for(intruder).post("/api/conversations", {"member_id": owner.pk, "body": "look", "upload_id": stolen.pk})
    assert r.status_code == 404 and not Message.objects.exists()


# -- conversations and messages -----------------------------------------------------------------------
@pytest.fixture
def chat(make_member, connect):
    a, b, outsider = make_member("student"), make_member("founder"), make_member("mentor")
    connect(a, b)
    x, y = sorted((a.pk, b.pk))
    conv = Conversation.objects.create(member_a_id=x, member_b_id=y, started_by=a, status="active")
    msg = Message.objects.create(conversation=conv, sender=a, body="private words")
    return a, b, outsider, conv, msg


def test_an_outsider_cannot_read_send_accept_block_or_mark_read(chat, client_for):
    _, _, outsider, conv, msg = chat
    c = client_for(outsider)
    base = f"/api/conversations/{conv.pk}"
    assert c.get(base).status_code == 404
    assert c.get(f"{base}/messages").status_code == 404
    assert c.get(f"{base}/messages/{msg.pk}").status_code == 404
    assert c.post(f"{base}/messages", {"body": "hi"}).status_code == 404
    assert c.post(f"{base}/accept").status_code == 404
    assert c.post(f"{base}/block").status_code == 404
    assert c.post(f"{base}/read").status_code == 404
    conv.refresh_from_db()
    assert conv.status == "active" and Message.objects.count() == 1
    assert c.get("/api/conversations").json() == []


def test_a_message_id_from_another_conversation_is_a_404(chat, make_member, connect, client_for):
    a, _, _, conv, msg = chat
    c3 = make_member("investor")
    connect(a, c3)
    x, y = sorted((a.pk, c3.pk))
    other = Conversation.objects.create(member_a_id=x, member_b_id=y, started_by=a, status="active")
    assert client_for(c3).get(f"/api/conversations/{other.pk}/messages/{msg.pk}").status_code == 404


def test_the_person_who_asked_cannot_accept_their_own_request(make_member, client_for):
    a, b = make_member("student"), make_member("founder")
    conv = client_for(a).post("/api/conversations", {"member_id": b.pk, "body": "hello"}).json()["conversation"]["id"]
    assert client_for(a).post(f"/api/conversations/{conv}/accept").status_code == 404
    assert client_for(b).post(f"/api/conversations/{conv}/accept").status_code == 200


def test_a_blocked_conversation_is_gone_for_both_sides(chat, client_for):
    a, b, _, conv, msg = chat
    assert client_for(b).post(f"/api/conversations/{conv.pk}/block").status_code == 204
    for who in (a, b):
        assert client_for(who).get(f"/api/conversations/{conv.pk}").status_code == 404
        assert client_for(who).get(f"/api/conversations/{conv.pk}/messages").status_code == 404
        assert client_for(who).post(f"/api/conversations/{conv.pk}/messages", {"body": "x"}).status_code == 404
    from apps.moderation.models import Block

    assert Block.objects.filter(blocker=b, blocked=a).exists()


# -- connection requests ------------------------------------------------------------------------------
def test_only_the_recipient_can_answer_a_connection_request(make_member, client_for):
    a, b, c = make_member("student"), make_member("founder"), make_member("mentor")
    req = ConnectionRequest.objects.create(sender=a, recipient=b, note="hi")
    for who in (a, c):  # the sender cannot accept their own request either
        assert client_for(who).post(f"/api/connections/requests/{req.pk}/respond", {"accept": True}).status_code == 404
    req.refresh_from_db()
    assert req.status == "pending"
    assert client_for(b).post(f"/api/connections/requests/{req.pk}/respond", {"accept": True}).status_code == 200


def test_connection_request_lists_show_only_my_own(make_member, client_for):
    a, b, c = make_member("student"), make_member("founder"), make_member("mentor")
    ConnectionRequest.objects.create(sender=a, recipient=b)
    assert len(client_for(b).get("/api/connections/requests").json()) == 1
    assert len(client_for(a).get("/api/connections/requests?box=outgoing").json()) == 1
    assert client_for(c).get("/api/connections/requests").json() == []
    assert client_for(c).get("/api/connections/requests?box=outgoing").json() == []


def test_removing_a_connection_needs_to_be_in_it(make_member, connect, client_for):
    a, b, c = make_member("student"), make_member("founder"), make_member("mentor")
    connect(a, b)
    assert client_for(c).delete(f"/api/connections/{a.pk}").status_code == 404
    assert client_for(a).delete(f"/api/connections/{b.pk}").status_code == 204


# -- daily drop ---------------------------------------------------------------------------
def test_only_people_in_my_own_drop_can_be_swiped(make_member, client_for):
    from django.utils import timezone

    from apps.social.drop import drop_day
    from apps.social.models import DailyDrop

    a, b, c = make_member("student"), make_member("founder"), make_member("mentor")
    DailyDrop.objects.create(
        member=b,
        date=drop_day(timezone.now()),
        candidates=[{"member_id": c.pk, "reason": "r", "is_bridge": False, "outcome": None}],
    )
    assert client_for(a).post(f"/api/drop/today/{c.pk}/swipe", {"direction": "skip"}).status_code == 404
    drop = DailyDrop.objects.get(member=b)
    assert drop.candidates[0]["outcome"] is None


# -- reports -----------------------------------------------------------------------------------------
def test_you_cannot_report_what_you_cannot_see(pair, make_post, chat, client_for):
    owner, intruder = pair
    hidden_post = make_post(owner, "connections")
    reply = Reply.objects.create(post=hidden_post, author=owner, body="x")
    _, _, outsider, conv, msg = chat
    c = client_for(intruder)
    for kind, ident in (("post", hidden_post.pk), ("reply", reply.pk), ("message", msg.pk)):
        assert c.post("/api/reports", {"target_type": kind, "target_id": ident, "reason": "spam"}).status_code == 404, kind
    assert (
        client_for(outsider).post("/api/reports", {"target_type": "message", "target_id": msg.pk, "reason": "spam"}).status_code
        == 404
    )
