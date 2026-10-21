from django.contrib.gis.db import models as gis
from django.db import models
from django.db.models import F, Q


class Role(models.TextChoices):
    STUDENT = "student"
    FOUNDER = "founder"
    MENTOR = "mentor"
    INVESTOR = "investor"
    PARTNER_ADMIN = "partner_admin"
    SUPER_ADMIN = "super_admin"


class Member(models.Model):
    class Visibility(models.TextChoices):
        PUBLIC = "public"
        MEMBERS = "members"
        HIDDEN = "hidden"

    auth_user_id = models.UUIDField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    display_name = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    location = gis.PointField(geography=False, srid=4326, null=True, blank=True)
    city = models.CharField(max_length=100, blank=True)
    college = models.CharField(max_length=200, blank=True)
    organisation = models.ForeignKey(
        "organisations.Organisation", null=True, blank=True, on_delete=models.SET_NULL, related_name="members"
    )
    verification_level = models.PositiveSmallIntegerField(default=1)
    open_intro_slots = models.PositiveSmallIntegerField(default=2)
    circuits_opt_in = models.BooleanField(default=False)
    is_minor = models.BooleanField(default=False)
    profile_visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.MEMBERS)
    visible_to_org = models.BooleanField(default=False)
    suspended_at = models.DateTimeField(null=True, blank=True)  # set = locked out of the API (moderation, takedowns)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(verification_level__gte=1, verification_level__lte=3),
                name="member_verification_level_1_3",
            )
        ]
        indexes = [models.Index(fields=["role"]), models.Index(fields=["city"])]

    def save(self, *args, **kwargs):
        # Under-18 members are hidden by default (CLAUDE.md privacy rules).
        if self._state.adding and self.is_minor and self.profile_visibility == self.Visibility.MEMBERS:
            self.profile_visibility = self.Visibility.HIDDEN
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Member {self.pk} ({self.role})"


class Connection(models.Model):
    """Undirected link between two members; stored once with member_a < member_b."""

    member_a = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="connections_a")
    member_b = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="connections_b")
    strength = models.FloatField(default=0.5)
    source = models.CharField(max_length=30, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["member_a", "member_b"], name="connection_unique_pair"),
            models.CheckConstraint(condition=Q(member_a__lt=F("member_b")), name="connection_ordered"),
            models.CheckConstraint(condition=Q(strength__gte=0, strength__lte=1), name="connection_strength_0_1"),
        ]
        indexes = [models.Index(fields=["member_b"])]


class Consent(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="consents")
    policy_version = models.CharField(max_length=20)
    accepted_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
