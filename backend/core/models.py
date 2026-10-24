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
