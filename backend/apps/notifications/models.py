from django.db import models


class Notification(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=40)
    payload = models.JSONField(default=dict)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["member", "-created_at"])]
