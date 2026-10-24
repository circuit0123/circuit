"""core/email.py: the outbox sends after commit, retries with backoff, and a flaky provider never fails the caller."""

from datetime import timedelta

import httpx
import pytest
from django.core import mail
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from apps.beta import services
from apps.beta.models import WaitlistEntry
from core import email as email_module
from core.models import OutboundEmail

pytestmark = pytest.mark.django_db
ADDRESS = "someone.private@example.org"


@pytest.fixture
def broken_provider(monkeypatch):
    """Every send fails the way a provider outage does."""
    calls = []

    def boom(self, fail_silently=False):
        calls.append(1)
        raise httpx.ConnectTimeout("resend is down")

    monkeypatch.setattr("django.core.mail.EmailMessage.send", boom)
    return calls


def test_an_email_is_sent_only_after_the_transaction_commits(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        with transaction.atomic():
            email_module.queue_email(ADDRESS, "test", "Hello", "Body text")
        assert mail.outbox == []
    for cb in callbacks:
        cb()
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert (msg.to, msg.subject, msg.body) == ([ADDRESS], "Hello", "Body text")
    row = OutboundEmail.objects.get()
    assert row.status == "sent" and row.attempts == 1 and row.sent_at is not None


def test_a_rolled_back_transaction_sends_nothing(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError), transaction.atomic():
            email_module.queue_email(ADDRESS, "test", "Hello", "Body")
            raise RuntimeError("something later in the request failed")
    assert mail.outbox == [] and not OutboundEmail.objects.exists()


def test_a_down_provider_does_not_fail_the_caller_and_the_row_waits(broken_provider, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        row = email_module.queue_email(ADDRESS, "test", "Hello", "Body")  # must not raise
    row.refresh_from_db()
    assert row.status == "pending" and row.attempts == 1 and row.last_error == "ConnectTimeout"
    assert row.next_attempt_at > timezone.now()


def test_the_job_retries_when_due_and_not_before(monkeypatch, django_capture_on_commit_callbacks):
    sent = []
    fail = {"on": True}

    def flaky(self, fail_silently=False):
        if fail["on"]:
            raise ConnectionError("down")
        sent.append(self.to)

    monkeypatch.setattr("django.core.mail.EmailMessage.send", flaky)
    with django_capture_on_commit_callbacks(execute=True):
        email_module.queue_email(ADDRESS, "test", "Hello", "Body")
    fail["on"] = False
    assert email_module.send_due() == {"due": 0, "sent": 0, "purged": 0}  # backoff has not elapsed
    OutboundEmail.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    assert email_module.send_due()["sent"] == 1 and sent == [[ADDRESS]]
    assert OutboundEmail.objects.get().status == "sent"
    assert email_module.send_due()["sent"] == 0  # idempotent: nothing is sent twice


def test_backoff_grows_and_it_gives_up_after_the_last_retry(broken_provider, settings, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        row = email_module.queue_email(ADDRESS, "test", "Hello", "Body")
    waits = []
    for _ in range(10):
        row.refresh_from_db()
        if row.status != "pending":
            break
        waits.append(round((row.next_attempt_at - timezone.now()).total_seconds() / 60))
        OutboundEmail.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        email_module.send_due()
    row.refresh_from_db()
    assert waits == [1, 5, 30, 120, 720]  # the delay before attempts 2..6
    assert row.status == "failed" and row.attempts == 6 == len(broken_provider)
    OutboundEmail.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    assert email_module.send_due()["due"] == 0  # failed rows are left alone


def test_finished_rows_are_purged_after_the_retention_window(settings):
    old = timezone.now() - timedelta(days=settings.EMAIL_KEEP_DAYS + 1)
    keep_pending = OutboundEmail.objects.create(
        to_email="a@example.org", kind="k", subject="s", body="b", next_attempt_at=old + timedelta(days=60)
    )
    for status in ("sent", "failed"):
        row = OutboundEmail.objects.create(
            to_email="a@example.org", kind="k", subject="s", body="b", status=status, next_attempt_at=old
        )
        OutboundEmail.objects.filter(pk=row.pk).update(created_at=old)
    OutboundEmail.objects.filter(pk=keep_pending.pk).update(created_at=old)
    assert email_module.send_due()["purged"] == 2
    assert list(OutboundEmail.objects.values_list("pk", flat=True)) == [keep_pending.pk]


def test_the_send_emails_command(capsys, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False):
        email_module.queue_email(ADDRESS, "test", "Hello", "Body")
    call_command("send_emails")
    assert "sent=1" in capsys.readouterr().out and len(mail.outbox) == 1


def test_nothing_personal_is_logged(broken_provider, capfd, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        row = email_module.queue_email(ADDRESS, "waitlist_invite", "Secret subject", "Secret body JOIN-CODE-123")
    OutboundEmail.objects.filter(pk=row.pk).update(attempts=5, next_attempt_at=timezone.now())
    email_module.send_due()  # the give-up warning
    out = capfd.readouterr().out
    assert "email_failed_will_retry" in out and "email_gave_up" in out
    for secret in (ADDRESS, "someone.private", "Secret subject", "JOIN-CODE-123"):
        assert secret not in out


# -- the invite email -----------------------------------------------------------------------------------
def make_entry(email="wait@example.org"):
    return WaitlistEntry.objects.create(email=email, role="student")


def staff_user():
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_superuser("mod", password="a-long-test-password-1")


def test_approving_sends_one_email_with_a_one_tap_link(settings, django_capture_on_commit_callbacks):
    settings.APP_URL = "https://app.example"
    entry = make_entry()
    with django_capture_on_commit_callbacks(execute=True):
        code = services.approve_waitlist(entry, staff_user())
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["wait@example.org"]
    assert f"https://app.example/join?code={code.code}&src=invite" in msg.body
    assert str(settings.INVITE_EXPIRY_DAYS_WAITLIST) in msg.body
    assert code.kind == "waitlist" and code.max_uses == 1 and code.expires_at is not None
    entry.refresh_from_db()
    assert entry.status == "approved" and entry.invite_code_id == code.pk


def test_approving_twice_sends_nothing_the_second_time(django_capture_on_commit_callbacks):
    entry, staff = make_entry(), staff_user()
    with django_capture_on_commit_callbacks(execute=True):
        services.approve_waitlist(entry, staff)
        assert services.approve_waitlist(entry, staff) is None
    assert len(mail.outbox) == 1


def test_approval_succeeds_when_resend_is_down(settings, monkeypatch, django_capture_on_commit_callbacks):
    settings.EMAIL_BACKEND = "core.email.ResendBackend"
    settings.RESEND_API_KEY = "re_test"
    monkeypatch.setattr(email_module.time, "sleep", lambda s: None)

    def down(*a, **kw):
        raise httpx.ConnectError("resend is down")

    monkeypatch.setattr(email_module.httpx, "post", down)
    entry = make_entry()
    with django_capture_on_commit_callbacks(execute=True):
        code = services.approve_waitlist(entry, staff_user())  # no exception
    entry.refresh_from_db()
    assert entry.status == "approved" and code is not None
    assert OutboundEmail.objects.get().status == "pending"  # the job will try again
    monkeypatch.setattr(email_module.httpx, "post", lambda *a, **kw: httpx.Response(200, json={"id": "x"}))
    OutboundEmail.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    assert email_module.send_due()["sent"] == 1


# -- ResendBackend ------------------------------------------------------------------------------------
def resend_message():
    return mail.EmailMessage("Hi", "Body", "Circuit <hello@example.com>", [ADDRESS])


@pytest.fixture
def resend(settings, monkeypatch):
    settings.RESEND_API_KEY = "re_secret"
    monkeypatch.setattr(email_module.time, "sleep", lambda s: None)
    return email_module.ResendBackend()


def test_resend_posts_the_message_with_a_timeout(resend, monkeypatch, settings):
    seen = {}

    def ok(url, **kw):
        seen.update(url=url, **kw)
        return httpx.Response(200, json={"id": "x"})

    monkeypatch.setattr(email_module.httpx, "post", ok)
    assert resend.send_messages([resend_message()]) == 1
    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["headers"] == {"Authorization": "Bearer re_secret"}
    assert seen["json"] == {"from": "Circuit <hello@example.com>", "to": [ADDRESS], "subject": "Hi", "text": "Body"}
    assert seen["timeout"] == settings.EMAIL_TIMEOUT_SECONDS


def test_resend_retries_once_on_a_5xx_then_succeeds(resend, monkeypatch):
    answers = [httpx.Response(503, request=httpx.Request("POST", "x")), httpx.Response(200, json={})]
    monkeypatch.setattr(email_module.httpx, "post", lambda *a, **kw: answers.pop(0))
    assert resend.send_messages([resend_message()]) == 1 and not answers


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ReadTimeout("slow"),
        httpx.Response(500, request=httpx.Request("POST", "x")),
        httpx.Response(429, request=httpx.Request("POST", "x")),
    ],
)
def test_resend_raises_after_its_attempts_so_the_outbox_can_retry_later(resend, monkeypatch, failure):
    calls = []

    def post(*a, **kw):
        calls.append(1)
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(email_module.httpx, "post", post)
    with pytest.raises(Exception):  # noqa: B017
        resend.send_messages([resend_message()])
    assert len(calls) == email_module.RESEND_ATTEMPTS


def test_resend_does_not_retry_a_message_the_provider_refused(resend, monkeypatch):
    calls = []
    monkeypatch.setattr(email_module.httpx, "post", lambda *a, **kw: calls.append(1) or httpx.Response(422, json={}))
    with pytest.raises(email_module.EmailRejected):
        resend.send_messages([resend_message()])
    assert len(calls) == 1
