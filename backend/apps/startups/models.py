from django.contrib.gis.db import models as gis
from django.db import models


class Startup(models.Model):
    class Source(models.TextChoices):
        SEED = "seed"
        CRAWLER = "crawler"
        USER = "user"

    name = models.CharField(max_length=200)
    website_domain = models.CharField(max_length=253, unique=True)
    description = models.TextField(blank=True)
    sector = models.CharField(max_length=80, blank=True)
    stage = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=300, blank=True)
    location = gis.PointField(srid=4326, null=True, blank=True)
    hiring = models.BooleanField(default=False)
    tech_stack = models.JSONField(default=list, blank=True)
    claimed_by = models.ForeignKey(
        "accounts.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="claimed_startups"
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.SEED)
    confidence = models.FloatField(default=1.0)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["hiring"]), models.Index(fields=["sector"])]

    def __str__(self) -> str:
        return self.name


class StartupMember(models.Model):
    startup = models.ForeignKey(Startup, on_delete=models.CASCADE, related_name="team")
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="startup_roles")
    role = models.CharField(max_length=80, default="founder")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["startup", "member"], name="startupmember_unique")]
        indexes = [models.Index(fields=["member"])]


class StartupTrait(models.Model):
    startup = models.ForeignKey(Startup, on_delete=models.CASCADE, related_name="traits")
    trait = models.ForeignKey("matching.Trait", on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["startup", "trait"], name="startuptrait_unique")]
        indexes = [models.Index(fields=["trait"])]


class StartupInterest(models.Model):
    startup = models.ForeignKey(Startup, on_delete=models.CASCADE, related_name="interests")
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="startup_interests")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["startup", "member"], name="startupinterest_unique")]
        indexes = [models.Index(fields=["member"])]


class ClaimRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        VERIFIED = "verified"
        EXPIRED = "expired"

    startup = models.ForeignKey(Startup, on_delete=models.CASCADE, related_name="claim_requests")
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="claim_requests")
    email_domain = models.CharField(max_length=253)
    token_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["startup"]), models.Index(fields=["member"])]
