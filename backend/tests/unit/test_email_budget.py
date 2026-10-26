"""Resend's free plan (100 a day, 3,000 a month) is a budget the app keeps: optional notification emails stop first and fall back
to in-app only, transactional email waits for the next day instead of failing. 0 means no limit."""

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core import mail
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import notify
from core import email as email_module
from core.models import OutboundEmail

pytestmark = pytest.mark.django_db
IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture(autouse=True)
def small_budget(settings):
    settings.EMAIL_DAILY_BUDGET, settings.EMAIL_MONTHLY_BUDGET = 3, 100
    settings.EMAIL_DAILY_LIMIT, settings.EMAIL_MONTHLY_LIMIT = 5, 200


@pytest.fixture
def queue(django_capture_on_commit_callbacks):
    """queue_email, with the send that normally happens after the transaction commits run straight away."""

    def _queue(*args, **kw):
        with django_capture_on_commit_callbacks(execute=True):
            return email_module.queue_email(*args, **kw)

    return _queue


def make_row(kind="notification.intros", status="sent", sent_at=None, created_at=None):
    row = OutboundEmail.objects.create(
        to_email="someone@example.org",
        kind=kind,
        subject="s",
        body="b",
        status=status,
        sent_at=sent_at,
        next_attempt_at=timezone.now(),
    )
    if created_at:
        OutboundEmail.objects.filter(pk=row.pk).update(created_at=created_at)
    return row


def fill(n, **kw):
    for _ in range(n):
        make_row(sent_at=timezone.now(), **kw)


# -- counting ------------------------------------------------------------------------------------
def test_usage_counts_queued_and_sent_today_and_this_month_but_not_failed():
    fill(2)
    make_row(status="pending")
    make_row(status="failed")
    assert email_module.usage() == {"queued_today": 3, "queued_month": 3, "sent_today": 2, "sent_month": 2}


def test_the_day_is_an_india_day():
    now = timezone.now().astimezone(IST).replace(hour=12, minute=0)
    this_morning = now.replace(hour=0, minute=30)
    yesterday = this_morning - timedelta(
        hours=2
    )  # 22:30 IST the day before: a different day, the same month unless it is the 1st
    make_row(status="sent", sent_at=this_morning, created_at=this_morning)
    make_row(status="sent", sent_at=yesterday, created_at=yesterday)
    used = email_module.usage(now)
    assert used["sent_today"] == 1 and used["queued_today"] == 1


def test_counts_start_again_the_next_day():
    row = make_row(
        status="sent", sent_at=timezone.now() - timedelta(days=1, hours=1), created_at=timezone.now() - timedelta(days=1, hours=1)
    )
    assert row.pk and email_module.usage()["sent_today"] == 0


# -- optional notification emails ----------------------------------------------------------------
def test_room_for_optional_email_until_the_daily_budget_is_reached():
    fill(2)
    assert email_module.has_room_for_optional()
    fill(1)
    assert not email_module.has_room_for_optional()


def test_the_monthly_budget_stops_optional_email_too(settings):
    settings.EMAIL_MONTHLY_BUDGET = 2
    fill(2)
    assert not email_module.has_room_for_optional()


def test_a_notification_over_budget_is_in_app_only(make_member):
    target = make_member("student", email="reader@example.org")
    fill(3)
    before = OutboundEmail.objects.count()
    row = notify(target, "intro.received", intro_id=1)
    assert row is not None and Notification.objects.filter(member=target).count() == 1  # the in-app notification is still there
    assert OutboundEmail.objects.count() == before  # but no email was queued


def test_a_notification_under_budget_still_sends_email(make_member):
    target = make_member("student", email="reader@example.org")
    notify(target, "intro.received", intro_id=1)
    assert OutboundEmail.objects.filter(kind="notification.intros").count() == 1


def test_no_limit_when_the_numbers_are_zero(settings, queue):
    settings.EMAIL_DAILY_BUDGET = settings.EMAIL_MONTHLY_BUDGET = settings.EMAIL_DAILY_LIMIT = settings.EMAIL_MONTHLY_LIMIT = 0
    fill(50)
    assert email_module.has_room_for_optional()
    queue("x@example.org", "invite", "s", "b")
    assert len(mail.outbox) == 1


# -- the provider's ceiling ----------------------------------------------------------------------
def test_transactional_email_still_goes_between_budget_and_limit(queue):
    fill(4)  # past the budget (3), under the limit (5)
    row = queue("x@example.org", "invite.code", "s", "b")
    row.refresh_from_db()
    assert row.status == "sent" and len(mail.outbox) == 1


def test_at_the_limit_transactional_email_waits_for_tomorrow_without_using_an_attempt(queue):
    fill(5)
    row = queue("x@example.org", "invite.code", "s", "b")
    row.refresh_from_db()
    assert row.status == "pending" and row.attempts == 0 and mail.outbox == []
    tomorrow = (timezone.now().astimezone(IST) + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
    assert abs(row.next_attempt_at.astimezone(IST) - tomorrow) < timedelta(minutes=2)
    assert email_module.send_due()["sent"] == 0  # not due yet: nothing is retried in a loop


def test_at_the_limit_an_optional_notification_email_is_dropped_not_deferred(queue):
    fill(5)
    row = queue("x@example.org", "notification.intros", "s", "b")
    row.refresh_from_db()
    assert row.status == "failed" and row.last_error == "BudgetExceeded" and mail.outbox == []


def test_after_midnight_the_waiting_email_goes_out(queue):
    fill(5)
    row = queue("x@example.org", "invite.code", "s", "b")
    OutboundEmail.objects.filter(sent_at__isnull=False).update(sent_at=timezone.now() - timedelta(days=1, hours=2))
    OutboundEmail.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now() - timedelta(minutes=1))
    assert email_module.send_due()["sent"] == 1


def test_the_monthly_limit_defers_too(settings, queue):
    settings.EMAIL_MONTHLY_LIMIT = 2
    fill(2)
    row = queue("x@example.org", "invite.code", "s", "b")
    row.refresh_from_db()
    assert row.status == "pending" and mail.outbox == []


def test_budgets_are_below_the_resend_free_plan_by_default():
    from circuit.config import Config

    fields = Config.model_fields
    assert (fields["email_daily_budget"].default, fields["email_daily_limit"].default) == (90, 100)
    assert (fields["email_monthly_budget"].default, fields["email_monthly_limit"].default) == (2800, 3000)
