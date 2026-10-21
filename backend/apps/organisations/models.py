from django.contrib.postgres.fields import ArrayField
from django.db import models


class Organisation(models.Model):
    class Kind(models.TextChoices):
        COLLEGE = "college"
        INCUBATOR = "incubator"
        PROGRAM = "program"

    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    city = models.CharField(max_length=100)
    email_domains = ArrayField(models.CharField(max_length=253), default=list, blank=True)
    join_code = models.CharField(max_length=32, unique=True)
    created_by = models.ForeignKey("accounts.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name
