from django.db import models


class CircuitRound(models.Model):
    week = models.CharField(max_length=10, unique=True, help_text="ISO week, e.g. 2026-W43")
    status = models.CharField(max_length=10, default="running")
    triggered_by = models.CharField(max_length=20, default="schedule")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Circuit(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed"
        ACTIVE = "active"
        COMPLETED = "completed"
        EXPIRED = "expired"
        DECLINED = "declined"

    round = models.ForeignKey(CircuitRound, on_delete=models.CASCADE, related_name="circuits")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PROPOSED)
    score = models.FloatField()
    consent_deadline = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "consent_deadline"])]


class CircuitLeg(models.Model):
    class Consent(models.TextChoices):
        PENDING = "pending"
        ACCEPTED = "accepted"
        DECLINED = "declined"

    circuit = models.ForeignKey(Circuit, on_delete=models.CASCADE, related_name="legs")
    giver = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="legs_given")
    receiver = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="legs_received")
    capability = models.ForeignKey("matching.Capability", on_delete=models.CASCADE, related_name="+")
    consent = models.CharField(max_length=10, choices=Consent.choices, default=Consent.PENDING)
    fulfilled = models.BooleanField(default=False)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["giver"]), models.Index(fields=["receiver"])]
