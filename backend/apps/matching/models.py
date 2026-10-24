from django.db import models
from django.db.models import Q
from pgvector.django import HnswIndex, VectorField

EMBEDDING_DIMS = 384


class Capability(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "capabilities"

    def __str__(self) -> str:
        return self.name


class Trait(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class MemberSkill(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="skills")
    capability = models.ForeignKey(Capability, on_delete=models.CASCADE, related_name="+")
    level = models.PositiveSmallIntegerField(default=1)
    proof_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["member", "capability"], name="memberskill_unique"),
            models.CheckConstraint(condition=Q(level__gte=1, level__lte=3), name="memberskill_level_1_3"),
        ]
        indexes = [models.Index(fields=["capability"])]


class MemberTrait(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="traits")
    trait = models.ForeignKey(Trait, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["member", "trait"], name="membertrait_unique")]
        indexes = [models.Index(fields=["trait"])]


class _NeedOffer(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="%(class)ss")
    capability = models.ForeignKey(Capability, on_delete=models.CASCADE, related_name="+")
    description = models.CharField(max_length=500, blank=True)
    embedding = VectorField(dimensions=EMBEDDING_DIMS, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Need(_NeedOffer):
    class Meta:
        constraints = [models.UniqueConstraint(fields=["member", "capability"], name="need_unique")]
        indexes = [
            models.Index(fields=["capability"]),
            HnswIndex(
                name="need_embedding_hnsw", fields=["embedding"], m=16, ef_construction=64, opclasses=["vector_cosine_ops"]
            ),
        ]


class Offer(_NeedOffer):
    class Meta:
        constraints = [models.UniqueConstraint(fields=["member", "capability"], name="offer_unique")]
        indexes = [
            models.Index(fields=["capability"]),
            HnswIndex(
                name="offer_embedding_hnsw", fields=["embedding"], m=16, ef_construction=64, opclasses=["vector_cosine_ops"]
            ),
        ]


class MatchResult(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="matches")
    candidate = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="+")
    score = models.FloatField()
    components = models.JSONField(default=dict)
    reason = models.CharField(max_length=300)
    is_bridge = models.BooleanField(default=False)
    computed_at = models.DateTimeField(auto_now=True)
    # Stage 4c: what the ranker saw and did, copied into feature_snapshots when the match is shown
    features = models.JSONField(default=dict, db_default={}, blank=True)
    position = models.PositiveIntegerField(default=0, db_default=0)  # 0-based place in this member's list, after ranking
    arm = models.CharField(max_length=10, default="rule", db_default="rule")  # "rule" or "model": which ranker ordered this list
    model_version = models.CharField(
        max_length=40, blank=True, db_default=""
    )  # the model that ordered (or, in shadow, scored) this list
    model_score = models.FloatField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["member", "candidate"], name="matchresult_unique")]
        indexes = [models.Index(fields=["member", "-score"]), models.Index(fields=["candidate"])]


class FeatureSnapshot(models.Model):
    """The exact numbers the ranker saw for one candidate shown to one member (CLAUDE.md "Matching ML").

    Training data is built from these rows, so it is the model's real input, not a reconstruction.
    One row per viewer, candidate, surface and day: refreshing a screen adds nothing.
    """

    class Surface(models.TextChoices):
        MATCHES = "matches"
        DAILY_DROP = "daily_drop"
        SIMULATION = "simulation"

    viewer = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="+")
    candidate = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="+")
    surface = models.CharField(max_length=12, choices=Surface.choices)
    model_version = models.CharField(max_length=40, blank=True)
    arm = models.CharField(max_length=10, default="rule")
    features = models.JSONField(default=dict)
    position = models.PositiveIntegerField(default=0)
    rule_score = models.FloatField()
    model_score = models.FloatField(null=True, blank=True)
    shown_at = models.DateTimeField()
    shown_on = models.DateField()  # the IST day, so a refresh on the same day does not add a row

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["viewer", "candidate", "surface", "shown_on"], name="featuresnapshot_unique")
        ]
        indexes = [models.Index(fields=["candidate"]), models.Index(fields=["shown_at"])]


SERVING_STATUSES = ("shadow", "ab", "active")


class ModelVersion(models.Model):
    """A trained ranker file and where it is in its life: candidate -> shadow -> ab -> active -> retired.

    Status changes go through `ranker.registry.promote`. `save()` repeats the production guard, so a form or a shell
    cannot put a model trained on simulated data in front of real users.
    """

    class Status(models.TextChoices):
        CANDIDATE = "candidate"
        SHADOW = "shadow"
        AB = "ab"
        ACTIVE = "active"
        RETIRED = "retired"

    class DataSource(models.TextChoices):
        REAL = "real"
        SIMULATED = "simulated"
        MIXED = "mixed"

    version = models.CharField(max_length=40, unique=True)
    trained_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CANDIDATE)
    metrics = models.JSONField(default=dict)
    file_path = models.CharField(max_length=300)  # inside the private bucket
    sha256 = models.CharField(max_length=64)
    data_source = models.CharField(max_length=10, choices=DataSource.choices)
    real_rows = models.PositiveIntegerField(default=0)
    simulated_rows = models.PositiveIntegerField(default=0)
    trained_env = models.CharField(max_length=12)
    data_hash = models.CharField(max_length=64, db_index=True)  # same data -> no new model (the job is idempotent)
    beats_rule = models.BooleanField(default=False)
    fairness_passed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # one model per serving slot: a new candidate can shadow while the active model keeps serving
            models.UniqueConstraint(fields=["status"], name="modelversion_one_per_slot", condition=Q(status__in=SERVING_STATUSES))
        ]

    def save(self, *args, **kwargs):
        from apps.matching.ranker.guard import refusal

        reason = refusal(self)
        if reason:
            raise ValueError(reason)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.version} ({self.status})"
