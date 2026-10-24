"""Stage 6: the one notification service. Preferences, feature flags, blocks and under-18 quiet hours each stop a send;
a provider outage never fails the request; every email carries a one-click unsubscribe."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
from django.core import mail
from django.utils import timezone

from apps.notifications import prefs
from apps.notifications.models import Notification
from apps.notifications.services import email_send_time, notify, notify_many
from core import email as email_module
from core import flags
from core.models import OutboundEmail

pytestmark = pytest.mark.django_db
IST = ZoneInfo("Asia/Kolkata")


def at(hour, minute=0):
    return datetime(2026, 10, 20, hour, minute, tzinfo=IST)


@pytest.fixture
def freeze(monkeypatch):
    def _freeze(moment):
        monkeypatch.setattr(timezone, "now", lambda: moment)

    return _freeze


def with_email(make_member, role="student", **kw):
    return make_member(role, email=kw.pop("email", "reader@example.org"), **kw)


def emails():
    return list(OutboundEmail.objects.order_by("id"))


# -- what is written -------------------------------------------------------------------------------
def test_an_intro_notification_writes_the_row_and_queues_an_email(
    make_member, realtime_events, django_capture_on_commit_callbacks
):
    asker, target = make_member("founder", display_name="Sneha"), with_email(make_member, "investor")
    with django_capture_on_commit_callbacks(execute=True):
        n = notify(target, "intro.received", actor=asker, intro_id=7)
    assert n is not None and n.payload == {"intro_id": 7, "actor_id": asker.pk}
    row = OutboundEmail.objects.get()
    assert (row.to_email, row.kind, row.member_id) == ("reader@example.org", "notification.intros", target.pk)
    assert "Sneha would like to meet you" in row.subject  # the actor's first name makes it specific
    assert realtime_events == [(f"member:{target.pk}", "notification", {"notification_id": n.pk})]
    assert len(mail.outbox) == 1  # sent right after commit


def test_every_notification_email_has_a_one_click_unsubscribe(make_member, settings):
    settings.API_URL, settings.APP_URL = "https://api.example", "https://app.example"
    target = with_email(make_member)
    notify(target, "application.status", application_id=1, status="shortlisted")
    row = OutboundEmail.objects.get()
    assert row.headers["List-Unsubscribe"].startswith("<https://api.example/api/unsubscribe?token=")
    assert row.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "https://app.example/unsubscribe?token=" in row.body and "https://app.example/settings/notifications" in row.body


def test_email_defaults_follow_the_preference_table(make_member):
    target = with_email(make_member)
    for kind in ("intro.received", "application.status", "circuit.proposed"):
        notify(target, kind, x=1)
    assert [e.kind for e in emails()] == ["notification.intros", "notification.applications", "notification.circuits"]
    OutboundEmail.objects.all().delete()
    for kind in ("message.new", "post.reply"):  # in-app only until the member opts in
        notify(target, kind, x=1)
    assert emails() == [] and Notification.objects.filter(member=target, kind__in=["message.new", "post.reply"]).count() == 2


def test_account_notices_are_in_app_only_and_always_on(make_member):
    target = with_email(make_member)
    target.notification_prefs = {t: {"in_app": False, "email": False} for t in prefs.TYPES}
    target.save()
    assert notify(target, "startup.claimed", startup_id=3) is not None
    assert emails() == []


def test_a_member_without_an_email_still_gets_the_in_app_notification(make_member):
    target = make_member("student")
    assert notify(target, "intro.received", intro_id=1) is not None and emails() == []


# -- preferences -----------------------------------------------------------------------------------
def test_email_off_for_a_type_sends_no_email_but_keeps_the_in_app_row(make_member):
    target = with_email(make_member, notification_prefs={"intros": {"in_app": True, "email": False}})
    assert notify(target, "intro.received", intro_id=1) is not None
    assert emails() == []


def test_in_app_off_for_a_type_writes_no_row_but_still_emails_if_email_is_on(make_member):
    target = with_email(make_member, notification_prefs={"intros": {"in_app": False, "email": True}})
    assert notify(target, "intro.received", intro_id=1) is None
    assert not Notification.objects.filter(member=target).exists() and len(emails()) == 1


def test_everything_off_sends_nothing_at_all(make_member):
    target = with_email(make_member, notification_prefs={t: {"in_app": False, "email": False} for t in prefs.TYPES})
    assert notify(target, "circuit.proposed", circuit_id=1) is None
    assert not Notification.objects.exists() and emails() == []


def test_a_preference_for_one_type_does_not_touch_another(make_member):
    target = with_email(make_member, notification_prefs={"intros": {"in_app": False, "email": False}})
    assert notify(target, "application.status", application_id=1) is not None and len(emails()) == 1


# -- feature flags ---------------------------------------------------------------------------------
def test_nothing_is_sent_for_a_feature_that_is_off(make_member, settings):
    settings.FEATURES = ",".join(f"{n}:everyone" for n in flags.FLAGS if n != "circuits")
    target = with_email(make_member)
    assert notify(target, "circuit.proposed", circuit_id=1) is None
    assert not Notification.objects.exists() and emails() == []
    assert notify(target, "intro.received", intro_id=1) is not None  # other features are unaffected


def test_the_testers_audience_gets_it_and_others_do_not(make_member, settings):
    settings.FEATURES = ",".join(f"{n}:{'testers' if n == 'circuits' else 'everyone'}" for n in flags.FLAGS)
    tester, other = with_email(make_member, is_tester=True), with_email(make_member, email="o@example.org")
    assert notify(tester, "circuit.activated", circuit_id=1) is not None
    assert notify(other, "circuit.activated", circuit_id=1) is None
    assert [e.to_email for e in emails()] == ["reader@example.org"]


def test_pulse_replies_follow_the_pulse_flag(make_member, settings):
    settings.FEATURES = "circuits:everyone"
    author = with_email(make_member, notification_prefs={"pulse_replies": {"in_app": True, "email": True}})
    assert notify(author, "post.reply", post_id=1) is None and emails() == []


# -- blocks ----------------------------------------------------------------------------------------
def test_a_block_stops_notifications_in_both_directions(make_member, block):
    a, b = with_email(make_member, email="a@example.org"), with_email(make_member, email="b@example.org")
    block(a, b)
    assert notify(a, "intro.received", actor=b, intro_id=1) is None  # a blocked b: b's actions do not reach a
    assert notify(b, "intro.received", actor=a, intro_id=1) is None  # and the other way round
    assert not Notification.objects.exists() and emails() == []


def test_a_block_hides_old_notifications_too(make_member, block, client_for):
    a, b = make_member("student"), make_member("founder")
    notify(a, "intro.received", actor=b, intro_id=1)
    assert client_for(a).get("/api/notifications").json()["count"] == 1
    block(b, a)
    assert client_for(a).get("/api/notifications").json()["count"] == 0
    assert client_for(a).get("/api/notifications/unread-count").json()["count"] == 0


def test_notifications_without_an_actor_are_never_hidden_by_a_block(make_member, block, client_for):
    a, b = make_member("student"), make_member("founder")
    notify(a, "circuit.proposed", circuit_id=1)
    block(a, b)
    assert client_for(a).get("/api/notifications").json()["count"] == 1


def test_people_are_not_notified_about_their_own_actions(make_member):
    a = with_email(make_member)
    assert notify(a, "intro.received", actor=a, intro_id=1) is None


def test_a_suspended_or_deleted_member_is_not_notified(make_member):
    gone = with_email(make_member, suspended_at=timezone.now())
    deleted = with_email(make_member, email="d@example.org", deleted_at=timezone.now())
    asked = with_email(make_member, email="e@example.org", deletion_requested_at=timezone.now())
    assert notify_many([gone, deleted, asked], "circuit.proposed", circuit_id=1) == 0
    assert not Notification.objects.exists() and emails() == []


def test_notify_many_tells_each_member_once(make_member):
    a, b = with_email(make_member), with_email(make_member, email="b@example.org")
    assert notify_many([a, b, a.pk], "circuit.proposed", circuit_id=1) == 2


# -- under-18 quiet hours --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (8, 59, at(9, 0)),  # too early: waits for 09:00 the same morning
        (9, 0, at(9, 0)),  # the first allowed minute: now
        (13, 30, at(13, 30)),
        (18, 59, at(18, 59)),
        (19, 0, at(9, 0) + timedelta(days=1)),  # the first blocked minute: waits for 09:00 tomorrow
        (23, 30, at(9, 0) + timedelta(days=1)),
        (2, 0, at(9, 0)),
    ],
)
def test_under_18_email_waits_for_09_00_ist_outside_09_to_19(make_member, freeze, hour, minute, expected):
    freeze(at(hour, minute))
    minor = with_email(make_member, is_minor=True)
    assert email_send_time(minor) == expected
    notify(minor, "intro.received", intro_id=1)
    assert emails()[0].next_attempt_at == expected


def test_adults_get_email_at_any_hour(make_member, freeze):
    freeze(at(23, 30))
    adult = with_email(make_member)
    notify(adult, "intro.received", intro_id=1)
    assert emails()[0].next_attempt_at == at(23, 30)


def test_a_waiting_under_18_email_is_not_sent_until_it_is_due(make_member, freeze, django_capture_on_commit_callbacks):
    freeze(at(21, 0))
    minor = with_email(make_member, is_minor=True)
    with django_capture_on_commit_callbacks(execute=True):
        notify(minor, "intro.received", intro_id=1)
    assert mail.outbox == [] and emails()[0].status == "pending" and emails()[0].attempts == 0  # nothing went out at 21:00
    assert email_module.send_due() == {"due": 0, "sent": 0, "purged": 0}
    freeze(at(9, 0) + timedelta(days=1, minutes=1))  # next morning
    assert email_module.send_due()["sent"] == 1 and len(mail.outbox) == 1


def test_the_in_app_notification_is_not_delayed_for_under_18s(make_member, freeze):
    freeze(at(22, 0))
    minor = with_email(make_member, is_minor=True)
    assert notify(minor, "intro.received", intro_id=1) is not None  # in-app is pull/Realtime, not a push or an email


# -- a provider outage -----------------------------------------------------------------------------
def test_resend_down_the_request_still_succeeds_and_the_email_retries(
    make_member, connect, client_for, settings, monkeypatch, django_capture_on_commit_callbacks
):
    settings.EMAIL_BACKEND = "core.email.ResendBackend"
    settings.RESEND_API_KEY = "re_test"
    monkeypatch.setattr(email_module.time, "sleep", lambda s: None)
    sent = []

    def down(*a, **kw):
        raise httpx.ConnectError("resend is down")

    monkeypatch.setattr(email_module.httpx, "post", down)
    asker, broker, target = make_member("founder"), with_email(make_member, "mentor"), make_member("investor")
    connect(asker, broker)
    connect(broker, target)
    with django_capture_on_commit_callbacks(execute=True):
        r = client_for(asker).post("/api/intros", {"target_id": target.pk, "message": "Could you introduce us?"})
    assert r.status_code == 201  # the action went through
    row = OutboundEmail.objects.get()
    assert row.status == "pending" and row.attempts == 1 and row.last_error == "ConnectError"
    assert Notification.objects.filter(member=broker, kind="intro.broker_request").exists()  # the in-app one is unaffected

    class Ok:
        status_code = 200

    monkeypatch.setattr(email_module.httpx, "post", lambda url, **kw: sent.append(kw["json"]) or Ok())
    OutboundEmail.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    assert email_module.send_due()["sent"] == 1
    assert sent[0]["to"] == ["reader@example.org"] and "List-Unsubscribe" in sent[0]["headers"]  # headers reach Resend
    row.refresh_from_db()
    assert row.status == "sent"


def test_a_failure_while_queuing_the_email_does_not_fail_the_notification(make_member, monkeypatch):
    target = with_email(make_member)

    def boom(*a, **kw):
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(email_module, "queue_email", boom)
    assert notify(target, "intro.received", intro_id=1) is not None  # the in-app row is written, nothing is raised
