"""Outgoing email that never fails the request that wanted it (PRODUCTION.md §14 row 7).

    queue_email(to, kind, subject, body, headers=None, member=None, send_at=None)

writes a row to the outbox and sends it once the surrounding transaction commits. If the provider is down the row stays
pending and `manage.py send_emails` (a job, every few minutes) retries with backoff, then gives up after the last retry.
Sending goes through Django's mail API, so dev prints to the console, demo drops it, tests use the in-memory outbox and
staging/production use ResendBackend below. No address or message text is ever logged.
"""

import time
from datetime import timedelta

import httpx
import structlog
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend
from django.db import transaction
from django.utils import timezone

from core.models import OutboundEmail

log = structlog.get_logger("email")

RESEND_URL = "https://api.resend.com/emails"
RESEND_ATTEMPTS = 2  # inside one send; the outbox adds its own, slower retries on top
RESEND_BACKOFF_SECONDS = 0.5


class EmailRejected(Exception):
    """The provider refused the message for good (a 4xx other than 429). Retrying the same message cannot help."""


class ResendBackend(BaseEmailBackend):
    """Django email backend that calls Resend's REST API: timeout, a quick retry on network errors/5xx/429, then it raises."""

    def send_messages(self, email_messages) -> int:
        sent = 0
        for message in email_messages:
            self._send(message)
            sent += 1
        return sent

    def _send(self, message) -> None:
        payload: dict = {"from": message.from_email, "to": list(message.to), "subject": message.subject, "text": message.body}
        if message.extra_headers:
            payload["headers"] = dict(message.extra_headers)  # e.g. List-Unsubscribe on notification emails
        headers = {"Authorization": f"Bearer {settings.RESEND_API_KEY}"}
        last: Exception | None = None
        for attempt in range(RESEND_ATTEMPTS):
            if attempt:
                time.sleep(RESEND_BACKOFF_SECONDS * 3**attempt)
            try:
                resp = httpx.post(RESEND_URL, json=payload, headers=headers, timeout=settings.EMAIL_TIMEOUT_SECONDS)
            except httpx.HTTPError as exc:
                last = exc
                continue
            if resp.status_code < 300:
                return
            if resp.status_code == 429 or resp.status_code >= 500:
                last = httpx.HTTPStatusError("provider unavailable", request=resp.request, response=resp)
                continue
            raise EmailRejected(f"HTTP {resp.status_code}")
        raise last or RuntimeError("email send failed")


def queue_email(
    to: str, kind: str, subject: str, body: str, *, headers: dict | None = None, member=None, send_at=None
) -> OutboundEmail:
    """Put an email in the outbox and try to send it right after the current transaction commits. Never raises for delivery.

    `send_at` in the future (quiet hours for under-18s) leaves it for the `send_emails` job, which sends it once it is due."""
    due = send_at or timezone.now()
    row = OutboundEmail.objects.create(
        to_email=to, kind=kind, subject=subject, body=body, headers=headers or {}, member=member, next_attempt_at=due
    )
    transaction.on_commit(lambda: deliver(row.pk))  # not due yet: deliver() leaves it pending
    return row


def deliver(email_id: int) -> bool:
    """One attempt for one pending email. Returns True if it was sent. Safe to call twice: a row lock stops double sends."""
    try:
        with transaction.atomic():
            row = (
                OutboundEmail.objects.select_for_update(skip_locked=True)
                .filter(pk=email_id, status=OutboundEmail.Status.PENDING, next_attempt_at__lte=timezone.now())
                .first()
            )
            if row is None:
                return False
            row.attempts += 1
            try:
                EmailMessage(row.subject, row.body, settings.EMAIL_FROM, [row.to_email], headers=row.headers or None).send(
                    fail_silently=False
                )
            except Exception as exc:
                _record_failure(row, exc)
                return False
            row.status = OutboundEmail.Status.SENT
            row.sent_at = timezone.now()
            row.last_error = ""
            row.save(update_fields=["attempts", "status", "sent_at", "last_error"])
            log.info("email_sent", email_id=row.pk, kind=row.kind)
            return True
    except Exception as exc:  # the database itself is unavailable: the caller must still succeed, the job will pick it up later
        log.warning("email_deliver_error", email_id=email_id, error=type(exc).__name__)
        return False


def _record_failure(row: OutboundEmail, exc: Exception) -> None:
    backoff = settings.EMAIL_RETRY_BACKOFF_MINUTES
    row.last_error = type(exc).__name__[:80]
    if row.attempts > len(backoff):
        row.status = OutboundEmail.Status.FAILED
        log.warning("email_gave_up", email_id=row.pk, kind=row.kind, attempts=row.attempts, error=row.last_error)
    else:
        row.next_attempt_at = timezone.now() + timedelta(minutes=backoff[row.attempts - 1])
        log.warning("email_failed_will_retry", email_id=row.pk, kind=row.kind, attempts=row.attempts, error=row.last_error)
    row.save(update_fields=["attempts", "status", "next_attempt_at", "last_error"])


def send_due(limit: int = 200) -> dict[str, int]:
    """The `send_emails` job: retry every pending email that is due, then delete old finished rows."""
    now = timezone.now()
    due = list(
        OutboundEmail.objects.filter(status=OutboundEmail.Status.PENDING, next_attempt_at__lte=now)
        .order_by("next_attempt_at")
        .values_list("pk", flat=True)[:limit]
    )
    sent = sum(deliver(pk) for pk in due)
    cutoff = now - timedelta(days=settings.EMAIL_KEEP_DAYS)
    purged, _ = OutboundEmail.objects.exclude(status=OutboundEmail.Status.PENDING).filter(created_at__lt=cutoff).delete()
    return {"due": len(due), "sent": sent, "purged": purged}
