from django.conf import settings
from django.db import models
from django.utils import timezone


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


class JobRun(models.Model):
    """One row per scheduled job: is it running right now, and how did its last run end.

    The row is also the job's LEASE. A run starts only if it can move `running_until` from the past to the future in one UPDATE
    (core/jobs.py), so when the scheduler retries or two runs overlap, exactly one does the work. A normal UPDATE works through
    Supabase's transaction pooler; session-level advisory locks would not, because the pooler hands out a different server
    connection for every transaction. A run that is killed (out of memory, timeout) never releases the lease, which simply expires."""

    name = models.CharField(max_length=60, primary_key=True)
    running_until = models.DateTimeField()
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_finished_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=10, blank=True, default="")  # running | ok | skipped | failed
    # Job health (core/jobhealth.py): a job is overdue when it has had no success for twice its interval.
    first_seen_at = models.DateTimeField(
        default=timezone.now
    )  # when check_jobs first saw the job: the clock for a job that never succeeded
    last_success_at = models.DateTimeField(null=True, blank=True)  # last run that ended ok, or looked and found nothing to do
    last_error = models.CharField(
        max_length=240, blank=True, default=""
    )  # exception class + short scrubbed message of the last failure; cleared on success


class UsageCounter(models.Model):
    """One counter per name per India day (core/usage.py): LLM calls today, so the daily cap holds across every instance and job.
    Counts only; no member, no text. Rows are tiny and a year of them is a few hundred."""

    name = models.CharField(max_length=40)
    day = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["name", "day"], name="usage_counter_name_day")]

    def __str__(self) -> str:
        return f"{self.name} {self.day}: {self.count}"
