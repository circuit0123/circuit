from django.conf import settings
from django.db import models


class RateLimitHit(models.Model):
    """Rate-limit fallback used only while Redis is down. Pruned on write; safe to truncate."""

    key = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["key", "created_at"]), models.Index(fields=["created_at"])]


class FeatureFlag(models.Model):
    """An admin override of a flag's default audience (the default comes from the FEATURES setting)."""

    AUDIENCES = [("off", "Off"), ("testers", "Testers"), ("everyone", "Everyone")]

    name = models.CharField(max_length=40, unique=True)
    audience = models.CharField(max_length=10, choices=AUDIENCES)
    note = models.CharField(max_length=200, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)


class OutboundEmail(models.Model):
    """Email outbox. An email is written here first and sent after commit; if the provider is down the row stays pending and
    `manage.py send_emails` retries with backoff, so a flaky provider never fails the request that wanted the email."""

    class Status(models.TextChoices):
        PENDING = "pending"
        SENT = "sent"
        FAILED = "failed"  # gave up after the last retry

    to_email = models.CharField(max_length=254)
    kind = models.CharField(max_length=40)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    headers = models.JSONField(default=dict, blank=True)  # extra mail headers, e.g. List-Unsubscribe (notification emails only)
    member = models.ForeignKey("accounts.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    last_error = models.CharField(
        max_length=80, blank=True
    )  # exception class name only, never a message that could hold an address
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "next_attempt_at"]), models.Index(fields=["created_at"])]

    def __str__(self) -> str:
        return f"Email #{self.pk} ({self.kind}, {self.status})"
