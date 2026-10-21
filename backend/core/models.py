from django.db import models


class RateLimitHit(models.Model):
    """Rate-limit fallback used only while Redis is down. Pruned on write; safe to truncate."""

    key = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["key", "created_at"]), models.Index(fields=["created_at"])]
