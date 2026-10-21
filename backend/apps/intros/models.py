from django.db import models


class IntroRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        ACCEPTED = "accepted"
        DECLINED = "declined"
        EXPIRED = "expired"
        COMPLETED = "completed"

    requester = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="intros_sent")
    target = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="intros_received")
    via = models.ForeignKey("accounts.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="intros_brokered")
    path = models.JSONField(default=list)
    message = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()
    outcome_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "expires_at"])]
