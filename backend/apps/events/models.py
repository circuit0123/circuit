from django.db import models


class Event(models.Model):
    """Append-only product events. A database trigger rejects UPDATE and DELETE."""

    actor = models.ForeignKey(
        "accounts.Member", null=True, blank=True, on_delete=models.DO_NOTHING, related_name="+", db_constraint=False
    )
    type = models.CharField(max_length=60)
    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.BigIntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["type", "-created_at"]), models.Index(fields=["actor"])]
