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

    class Meta:
        constraints = [models.UniqueConstraint(fields=["member", "candidate"], name="matchresult_unique")]
        indexes = [models.Index(fields=["member", "-score"]), models.Index(fields=["candidate"])]
