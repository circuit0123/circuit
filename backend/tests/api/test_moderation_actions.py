"""Stage 6: the Django admin moderation queue. Hide, remove, warn, suspend and dismiss, for posts, replies, messages, members and
startups. Every action closes the report, records what was done, and is audit-logged."""

import json

import pytest
from django.contrib import admin

from apps.events.models import Event
from apps.jobs.models import Job
from apps.messaging.models import Conversation, Message
from apps.moderation.models import AuditLog, Report
from apps.notifications.models import Notification
from apps.social.models import Post, Reply
from core.models import OutboundEmail
from tests.api.test_reports import report

pytestmark = pytest.mark.django_db


def queue():
    return admin.site._registry[Report]


def act(request, rep, name):
    getattr(queue(), name)(request, Report.objects.filter(pk=rep.pk))
    rep.refresh_from_db()
    return rep


def file_report(client_for, reporter, kind, ident):
    r = report(client_for(reporter), kind, ident)
    assert r.status_code == 201, r.content
    return Report.objects.get(pk=r.json()["id"])


def test_the_queue_offers_exactly_the_five_actions():
    assert queue().actions == ("hide", "remove", "warn", "suspend", "dismiss")


# -- every action closes the report and says what happened -----------------------------------------------
@pytest.mark.parametrize("action", ["hide", "remove", "warn", "suspend", "dismiss"])
def test_every_action_closes_the_report_records_the_action_and_is_audit_logged(
    action,
    make_member,
    make_post,
    client_for,
    staff_request,
):
    request, staff = staff_request
    author = make_member("founder", email="author@example.org")
    rep = act(request, file_report(client_for, make_member("student"), "post", make_post(author, "everyone").pk), action)
    assert rep.action == action and rep.handled_by == staff and rep.handled_at is not None
    assert rep.status == ("dismissed" if action == "dismiss" else "actioned")
    assert AuditLog.objects.filter(actor=staff, action=action, target_id=str(rep.pk)).exists()
    assert Event.objects.filter(type="report.actioned", payload__action=action, payload__report_id=rep.pk).exists()


# -- hide / remove ---------------------------------------------------------------------------------------
def test_hide_hides_a_post_and_remove_removes_it(make_member, make_post, client_for, staff_request):
    request, _ = staff_request
    reporter, author = make_member("student"), make_member("founder")
    hidden_post, removed_post = make_post(author, "everyone"), make_post(author, "everyone")
    act(request, file_report(client_for, reporter, "post", hidden_post.pk), "hide")
    act(request, file_report(client_for, reporter, "post", removed_post.pk), "remove")
    assert Post.objects.get(pk=hidden_post.pk).status == "hidden" and Post.objects.get(pk=removed_post.pk).status == "removed"
    assert client_for(reporter).get(f"/api/posts/{hidden_post.pk}").status_code == 404
    assert (
        client_for(author).get(f"/api/posts/{hidden_post.pk}").json()["status"] == "hidden"
    )  # the author can still see what happened


def test_hide_and_remove_a_reply(make_member, make_post, client_for, staff_request):
    request, _ = staff_request
    post = make_post(make_member("founder"), "everyone")
    one, two = (Reply.objects.create(post=post, author=post.author, body=f"spam {i}") for i in range(2))
    reporter = make_member("student")
    act(request, file_report(client_for, reporter, "reply", one.pk), "hide")
    act(request, file_report(client_for, reporter, "reply", two.pk), "remove")
    assert (Reply.objects.get(pk=one.pk).status, Reply.objects.get(pk=two.pk).status) == ("hidden", "removed")


def test_hide_and_remove_blank_a_message_for_both_people(make_member, connect, client_for, staff_request):
    request, _ = staff_request
    a, b = make_member("founder"), make_member("student")
    connect(a, b)
    first = client_for(a).post("/api/conversations", {"member_id": b.pk, "body": "pay me"}).json()
    second = client_for(a).post(f"/api/conversations/{first['conversation']['id']}/messages", {"body": "pay me now"}).json()
    act(request, file_report(client_for, b, "message", first["message"]["id"]), "hide")
    act(request, file_report(client_for, b, "message", second["id"]), "remove")
    assert not Message.objects.filter(conversation_id=first["conversation"]["id"], removed_at__isnull=True).exists()
    shown = client_for(b).get(f"/api/conversations/{first['conversation']['id']}/messages").json()["items"]
    assert all(m["removed"] and m["body"] == "" for m in shown)


def test_hide_takes_a_member_profile_out_of_sight_but_remove_does_nothing_to_a_member(make_member, client_for, staff_request):
    request, _ = staff_request
    target, other = make_member("founder"), make_member("mentor")
    rep = act(request, file_report(client_for, other, "member", target.pk), "hide")
    target.refresh_from_db()
    assert target.profile_visibility == "hidden" and client_for(other).get(f"/api/members/{target.pk}").status_code == 404
    again = make_member("mentor")
    other_target = make_member("founder")
    rep2 = act(request, file_report(client_for, again, "member", other_target.pk), "remove")
    other_target.refresh_from_db()
    assert other_target.profile_visibility == "members" and rep2.status == "actioned" and rep.status == "actioned"
    assert (
        AuditLog.objects.get(action="remove", target_id=str(rep2.pk)).payload["changed"] is False
    )  # the log says nothing changed


# -- startups --------------------------------------------------------------------------------------------
def test_a_member_can_report_a_startup_but_not_their_own_or_a_hidden_one(make_member, make_startup, client_for):
    founder, student = make_member("founder"), make_member("student")
    startup = make_startup(claimed_by=founder)
    from apps.startups.models import StartupMember

    StartupMember.objects.create(startup=startup, member=founder)
    assert report(client_for(student), "startup", startup.pk).status_code == 201
    assert report(client_for(founder), "startup", startup.pk).status_code == 404  # the team cannot report itself
    assert report(client_for(student), "startup", 999999).status_code == 404
    startup.hidden_at = startup.created_at
    startup.save()
    assert report(client_for(make_member("mentor")), "startup", startup.pk).status_code == 404


@pytest.mark.parametrize("action", ["hide", "remove"])
def test_a_hidden_startup_disappears_from_the_map_search_detail_and_roles(
    action, make_member, make_startup, client_for, staff_request
):
    request, _ = staff_request
    student = make_member("student")
    startup = make_startup(name="Shady Co", hiring=True)
    Job.objects.create(startup=startup, title="Intern", kind="internship", is_open=True)
    c = client_for(student)
    assert any(s["id"] == startup.pk for s in c.get("/api/startups/nearby?lat=13.08&lng=80.27&radius_km=10").json())
    assert c.get(f"/api/startups/{startup.pk}").status_code == 200 and c.get("/api/jobs").json()["count"] == 1
    act(request, file_report(client_for, student, "startup", startup.pk), action)
    startup.refresh_from_db()
    assert startup.hidden_at is not None
    assert not any(s["id"] == startup.pk for s in c.get("/api/startups/nearby?lat=13.08&lng=80.27&radius_km=10").json())
    assert "Shady Co" not in c.get("/api/startups/map?min_lng=80&min_lat=13&max_lng=80.5&max_lat=13.5").content.decode()
    assert c.get(f"/api/startups/{startup.pk}").status_code == 404
    assert c.get("/api/jobs").json()["count"] == 0


# -- warn ------------------------------------------------------------------------------------------------
def test_warn_tells_the_author_in_the_app_and_by_email_regardless_of_email_preferences(
    make_member, make_post, client_for, staff_request, settings
):
    request, _ = staff_request
    settings.APP_URL = "https://app.example"
    author = make_member(
        "founder",
        email="author@example.org",
        notification_prefs={t: {"in_app": False, "email": False} for t in ("intros", "messages")},
    )
    rep = act(request, file_report(client_for, make_member("student"), "post", make_post(author, "everyone").pk), "warn")
    note = Notification.objects.get(member=author)
    assert note.kind == "moderation.warning" and note.payload == {"report_id": rep.pk}  # no names, no reporter, no content
    mail_row = OutboundEmail.objects.get(kind="moderation.warning")
    assert mail_row.to_email == "author@example.org" and "https://app.example/help/community-guidelines" in mail_row.body
    assert "List-Unsubscribe" not in mail_row.headers  # a safety notice is not a marketing type
    assert "student" not in mail_row.body.lower() and "reported" not in mail_row.body.lower()  # the reporter stays anonymous


def test_warn_on_a_startup_goes_to_its_claimant_and_on_an_unclaimed_one_to_nobody(
    make_member, make_startup, client_for, staff_request
):
    request, _ = staff_request
    founder, student = make_member("founder"), make_member("student")
    claimed, unclaimed = make_startup(name="A", domain="a.io", claimed_by=founder), make_startup(name="B", domain="b.io")
    act(request, file_report(client_for, student, "startup", claimed.pk), "warn")
    act(request, file_report(client_for, student, "startup", unclaimed.pk), "warn")
    assert Notification.objects.filter(kind="moderation.warning").count() == 1 and Notification.objects.get().member == founder
    assert AuditLog.objects.filter(action="warn", payload__changed=False).count() == 1


# -- suspend ---------------------------------------------------------------------------------------------
def test_suspend_locks_the_author_out_at_once(make_member, make_post, client_for, staff_request):
    request, _ = staff_request
    author = make_member("founder", visible_to_org=True)
    assert client_for(author).get("/api/me").status_code == 200
    act(request, file_report(client_for, make_member("student"), "post", make_post(author, "everyone").pk), "suspend")
    author.refresh_from_db()
    assert author.suspended_at is not None and author.visible_to_org is False
    r = client_for(author).get("/api/me")
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_suspended"


def test_suspend_on_a_startup_suspends_the_claimant_and_never_a_super_admin(
    make_member, make_startup, make_post, client_for, staff_request
):
    request, _ = staff_request
    student, founder, admin_member = make_member("student"), make_member("founder"), make_member("super_admin")
    act(request, file_report(client_for, student, "startup", make_startup(claimed_by=founder).pk), "suspend")
    founder.refresh_from_db()
    assert founder.suspended_at is not None
    post = make_post(admin_member, "everyone")
    rep = Report.objects.create(reporter=student, target_type="post", target_id=post.pk, reason="x")
    act(request, rep, "suspend")
    admin_member.refresh_from_db()
    assert admin_member.suspended_at is None and AuditLog.objects.filter(action="suspend", payload__changed=False).exists()


def test_dismiss_changes_nothing_but_the_report(make_member, make_post, client_for, staff_request):
    request, _ = staff_request
    author = make_member("founder")
    post = make_post(author, "everyone")
    rep = act(request, file_report(client_for, make_member("student"), "post", post.pk), "dismiss")
    assert rep.status == "dismissed" and Post.objects.get(pk=post.pk).status == "visible"
    author.refresh_from_db()
    assert author.suspended_at is None and not Notification.objects.exists()


def test_acting_twice_on_the_same_report_is_harmless(make_member, make_post, client_for, staff_request):
    request, _ = staff_request
    rep = file_report(client_for, make_member("student"), "post", make_post(make_member("founder"), "everyone").pk)
    act(request, rep, "remove")
    act(request, rep, "remove")
    assert Post.objects.get(pk=rep.target_id).status == "removed" and AuditLog.objects.filter(action="remove").count() == 2


def test_the_report_page_shows_what_was_reported_for_every_kind(make_member, make_post, make_startup, client_for):
    student = make_member("student")
    author = make_member("founder")
    startup = make_startup(name="Shown Co")
    previews = [
        queue().target_preview(file_report(client_for, student, "startup", startup.pk)),
        queue().target_preview(file_report(client_for, student, "post", make_post(author, "everyone", body="look at this").pk)),
    ]
    assert "Shown Co" in previews[0] and "look at this" in previews[1]
    conv = Conversation.objects.create(
        member_a_id=min(student.pk, author.pk), member_b_id=max(student.pk, author.pk), started_by=author, status="active"
    )
    msg = Message.objects.create(conversation=conv, sender=author, body="the message")
    assert "the message" in queue().target_preview(file_report(client_for, student, "message", msg.pk))
    assert json.dumps(previews)  # plain strings: nothing that can break the admin page
