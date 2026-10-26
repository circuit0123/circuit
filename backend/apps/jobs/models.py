from django.db import models
from django.db.models import Q


class Job(models.Model):
    class Kind(models.TextChoices):
        INTERNSHIP = "internship"
        FULL_TIME = "full_time"
        PART_TIME = "part_time"

    startup = models.ForeignKey("startups.Startup", on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.INTERNSHIP)
    description = models.TextField(blank=True)
    stipend_min = models.PositiveIntegerField(null=True, blank=True, help_text="INR per month")
    stipend_max = models.PositiveIntegerField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    duration_weeks = models.PositiveSmallIntegerField(null=True, blank=True)  # how long the role runs; blank = open-ended
    starts_on = models.DateField(null=True, blank=True)
    is_open = models.BooleanField(default=True)
    posted_by = models.ForeignKey("accounts.Member", null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["is_open", "kind"])]


class JobCapability(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="capabilities")
    capability = models.ForeignKey("matching.Capability", on_delete=models.CASCADE, related_name="+")
    required = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "capability"], name="jobcapability_unique")]
        indexes = [models.Index(fields=["capability"])]


class Application(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied"
        SHORTLISTED = "shortlisted"
        REJECTED = "rejected"
        HIRED = "hired"
        WITHDRAWN = "withdrawn"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    student = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="applications")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.APPLIED)
    skill_match = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "student"], name="application_unique"),
            models.CheckConstraint(condition=Q(skill_match__gte=0, skill_match__lte=1), name="application_match_0_1"),
        ]
        indexes = [models.Index(fields=["student"]), models.Index(fields=["job", "-skill_match"])]
