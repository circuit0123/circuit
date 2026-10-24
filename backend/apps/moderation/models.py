from django.conf import settings
from django.db import models


class Report(models.Model):
    class Status(models.TextChoices):
        OPEN = "open"
        ACTIONED = "actioned"
        DISMISSED = "dismissed"

    reporter = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="reports_filed")
    target_type = models.CharField(max_length=30)
    target_id = models.BigIntegerField()
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)

    class Action(models.TextChoices):
        HIDE = "hide"
        REMOVE = "remove"
        WARN = "warn"
        SUSPEND = "suspend"
        DISMISS = "dismiss"

    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=10, choices=Action.choices, blank=True)  # what the moderator did; blank while open
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["target_type", "target_id"]), models.Index(fields=["status"])]


class Block(models.Model):
    blocker = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="blocks")
    blocked = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="blocked_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["blocker", "blocked"], name="block_unique")]
        indexes = [models.Index(fields=["blocked"])]


class AuditLog(models.Model):
    """Every super-admin action. Written by the admin and by services; never edited."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60)
    target_type = models.CharField(max_length=60)
    target_id = models.CharField(max_length=40)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["target_type", "target_id"]), models.Index(fields=["-created_at"])]
