import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.cookie import CookieStorage

from apps.events.models import Event
from apps.messaging.models import Conversation, Message
from apps.moderation.models import AuditLog, Report
from apps.social.models import Post, Reply

pytestmark = pytest.mark.django_db


def report(client, kind, ident, reason="This is spam"):
    return client.post("/api/reports", {"target_type": kind, "target_id": ident, "reason": reason})


def test_report_a_post_a_reply_a_message_and_a_member(make_member, make_post, connect, client_for):
    author, me = make_member("founder"), make_member("student")
    post = make_post(author, "everyone")
    reply = Reply.objects.create(post=post, author=author, body="buy followers")
    connect(me, author)
    x, y = sorted((me.pk, author.pk))
    conv = Conversation.objects.create(member_a_id=x, member_b_id=y, started_by=author, status="active")
    msg = Message.objects.create(conversation=conv, sender=author, body="send money")
    c = client_for(me)
    for kind, ident in (("post", post.pk), ("reply", reply.pk), ("message", msg.pk), ("member", author.pk)):
        r = report(c, kind, ident)
        assert r.status_code == 201 and r.json()["status"] == "open" and r.json()["target_type"] == kind, kind
    assert Report.objects.filter(reporter=me).count() == 4
    assert Event.objects.filter(type="report.created").count() == 4


def test_reporting_twice_returns_the_open_report(make_member, make_post, client_for):
    author, me = make_member("founder"), make_member("student")
    post = make_post(author, "everyone")
    first, second = report(client_for(me), "post", post.pk), report(client_for(me), "post", post.pk, "again")
    assert first.json()["id"] == second.json()["id"] and Report.objects.count() == 1


def test_cannot_report_yourself_or_your_own_content(make_member, make_post, client_for):
    me = make_member("student")
    c = client_for(me)
    assert report(c, "member", me.pk).status_code == 404
    assert report(c, "post", make_post(me, "everyone").pk).status_code == 404


def test_validation(make_member, make_post, client_for):
    me, other = make_member("student"), make_member("founder")
    post = make_post(other, "everyone")
    c = client_for(me)
    assert report(c, "post", post.pk, "").status_code == 422
    assert report(c, "post", post.pk, "x" * 501).status_code == 422
    assert report(c, "job", post.pk).status_code == 422
    assert report(c, "post", 999999).status_code == 404


def test_report_rate_limit(make_member, make_post, client_for, settings):
    settings.RATE_LIMITS = {**settings.RATE_LIMITS, "report": (2, 60)}
    me, other = make_member("student"), make_member("founder")
    codes = [report(client_for(me), "post", make_post(other, "everyone").pk).status_code for _ in range(3)]
    assert codes == [201, 201, 429]


def test_a_member_i_can_only_reach_through_a_request_can_still_be_reported(make_member, client_for):
    from apps.accounts.models import ConnectionRequest

    me = make_member("student", profile_visibility="hidden")
    hidden_sender = make_member("mentor", profile_visibility="hidden")
    assert report(client_for(me), "member", hidden_sender.pk).status_code == 404
    ConnectionRequest.objects.create(sender=hidden_sender, recipient=me, note="hi")
    assert report(client_for(me), "member", hidden_sender.pk).status_code == 201


# -- moderation in Django admin ---------------------------------------------------------------------
@pytest.fixture
def staff_request(rf):
    staff = get_user_model().objects.create_superuser("mod", password="a-long-test-password-1")
    request = rf.post("/")
    request.user = staff
    request._messages = CookieStorage(request)
    return request, staff


def test_hide_remove_and_restore_posts_and_replies_are_audit_logged(make_member, make_post, staff_request):
    request, staff = staff_request
    post = make_post(make_member("founder"), "everyone")
    reply = Reply.objects.create(post=post, author=post.author, body="x")
    pa, ra = admin.site._registry[Post], admin.site._registry[Reply]
    pa.hide(request, Post.objects.filter(pk=post.pk))
    post.refresh_from_db()
    assert post.status == "hidden"
    pa.restore(request, Post.objects.filter(pk=post.pk))
    pa.remove(request, Post.objects.filter(pk=post.pk))
    ra.remove(request, Reply.objects.filter(pk=reply.pk))
    post.refresh_from_db()
    reply.refresh_from_db()
    assert post.status == "removed" and reply.status == "removed"
    actions = list(AuditLog.objects.filter(actor=staff).order_by("id").values_list("action", "target_type"))
    assert actions == [("hide", "social.post"), ("restore", "social.post"), ("remove", "social.post"), ("remove", "social.reply")]


def test_a_removed_post_disappears_for_everyone_but_the_author(make_member, make_post, staff_request, client_for):
    request, _ = staff_request
    author, reader = make_member("founder"), make_member("student")
    post = make_post(author, "everyone")
    admin.site._registry[Post].remove(request, Post.objects.filter(pk=post.pk))
    assert client_for(reader).get(f"/api/posts/{post.pk}").status_code == 404
    assert client_for(reader).get(f"/api/members/{author.pk}/posts").json() == []
    assert client_for(author).get(f"/api/posts/{post.pk}").json()["status"] == "removed"


def test_report_admin_shows_the_reported_message_and_takes_it_down(make_member, connect, client_for, staff_request):
    request, staff = staff_request
    a, b = make_member("founder"), make_member("student")
    connect(a, b)
    cid = client_for(a).post("/api/conversations", {"member_id": b.pk, "body": "pay me now"}).json()
    msg_id = cid["message"]["id"]
    r = client_for(b).post("/api/reports", {"target_type": "message", "target_id": msg_id, "reason": "scam"})
    rep = Report.objects.get(pk=r.json()["id"])
    ra = admin.site._registry[Report]
    assert "pay me now" in ra.target_preview(rep)  # the only place a moderator can read a DM
    ra.take_down(request, Report.objects.filter(pk=rep.pk))
    rep.refresh_from_db()
    assert rep.status == "actioned" and rep.handled_by == staff
    assert Message.objects.get(pk=msg_id).removed_at is not None
    shown = client_for(b).get(f"/api/conversations/{cid['conversation']['id']}/messages").json()["items"][0]
    assert shown["removed"] is True and shown["body"] == ""  # hidden from both sides
    assert AuditLog.objects.filter(actor=staff, action="take_down", target_id=str(rep.pk)).exists()


def test_dismissing_a_report_changes_nothing_else(make_member, make_post, client_for, staff_request):
    request, staff = staff_request
    post = make_post(make_member("founder"), "everyone")
    rid = report(client_for(make_member("student")), "post", post.pk).json()["id"]
    admin.site._registry[Report].dismiss(request, Report.objects.filter(pk=rid))
    assert Report.objects.get(pk=rid).status == "dismissed" and Post.objects.get(pk=post.pk).status == "visible"


def test_messages_are_not_browsable_in_admin_and_conversations_are_read_only():
    from apps.messaging.models import Conversation

    assert Message not in admin.site._registry
    ca = admin.site._registry[Conversation]
    assert not ca.has_add_permission(None) and not ca.has_change_permission(None) and not ca.has_delete_permission(None)
