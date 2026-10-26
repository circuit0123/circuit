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
    headline = models.CharField(
        max_length=140, blank=True, db_default=""
    )  # one line under the name ("Frontend developer, building a voice assistant"); blank = the first line of the bio (headline_line)
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
    is_tester = models.BooleanField(default=False)  # set by a super admin; the `testers` flag audience
    profile_visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.MEMBERS)
    visible_to_org = models.BooleanField(default=False)
    suspended_at = models.DateTimeField(null=True, blank=True)  # set = locked out of the API (moderation, takedowns)
    pulse_seen_at = models.DateTimeField(null=True, blank=True)  # Pulse shows what is newer than this, then "You're caught up"
    email = models.EmailField(blank=True)  # copied from the verified sign-in email; only used to send mail. Cleared on deletion
    appearance = models.JSONField(
        default=dict, blank=True
    )  # theme, accent, swipe_tabs; missing keys mean the defaults (appearance.py)
    notification_prefs = models.JSONField(
        default=dict, blank=True
    )  # type -> {in_app, email}; missing keys mean the defaults (prefs.py)
    photo_path = models.CharField(
        max_length=200, blank=True, db_default=""
    )  # folder of the profile photo in the avatars bucket (MediaUpload.path); blank = the circuit-pattern avatar
    read_receipts = models.BooleanField(
        default=False, db_default=False
    )  # show read ticks on my messages; each person sees them only when both have it on (messaging/services.py)
    allow_requests = models.BooleanField(default=True)  # False: strangers cannot send message requests or connection requests
    deletion_requested_at = models.DateTimeField(
        null=True, blank=True
    )  # set = locked out; the delete_accounts job finishes the job
    deleted_at = models.DateTimeField(
        null=True, blank=True
    )  # set = anonymised "Deleted member" tombstone that old content points at
    onboarding = models.JSONField(
        default=dict, db_default={}, blank=True
    )  # current_step, completed_at, answers (one key per step); lets the app resume mid-flow (onboarding_state.py)
    signup_source = models.CharField(
        max_length=40, blank=True, db_default=""
    )  # the landing page or invite that brought them; first touch wins
    is_simulated = models.BooleanField(
        default=False, db_default=False
    )  # synthetic member from `simulate_network`; never matched with real people
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(verification_level__gte=1, verification_level__lte=3),
                name="member_verification_level_1_3",
            )
        ]
        indexes = [models.Index(fields=["role"]), models.Index(fields=["city"]), models.Index(fields=["is_simulated"])]

    def save(self, *args, **kwargs):
        # Under-18 members are hidden by default (CLAUDE.md privacy rules).
        if self._state.adding and self.is_minor and self.profile_visibility == self.Visibility.MEMBERS:
            self.profile_visibility = self.Visibility.HIDDEN
        if self._state.adding and self.is_minor:
            self.allow_requests = False  # no Requests from strangers for under-18s (DESIGN.md §4 Inbox)
        super().save(*args, **kwargs)

    def headline_line(self) -> str:
        """The line shown under the name: their headline, or the start of their bio when they have not written one."""
        return self.headline.strip() or (self.bio or "").strip()[:140]

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


class ConnectionRequest(models.Model):
    """Ask to connect, with a note. Accepting creates the Connection row; declining keeps this row so the sender cannot spam."""

    class Status(models.TextChoices):
        PENDING = "pending"
        ACCEPTED = "accepted"
        DECLINED = "declined"

    sender = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="connection_requests_sent")
    recipient = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="connection_requests_received")
    note = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sender", "recipient"], condition=Q(status="pending"), name="connectionrequest_one_pending"
            ),
            models.CheckConstraint(condition=~Q(sender=F("recipient")), name="connectionrequest_not_self"),
        ]
        indexes = [models.Index(fields=["recipient", "status"]), models.Index(fields=["sender", "status"])]


class Consent(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="consents")
    policy_version = models.CharField(max_length=20)
    accepted_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class DataExport(models.Model):
    """One request for 'all my data' (DPDP). A job builds the zip; the member downloads it with a signed, expiring link."""

    class Status(models.TextChoices):
        PENDING = "pending"
        BUILDING = "building"
        READY = "ready"
        FAILED = "failed"
        EXPIRED = "expired"

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="exports")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    path = models.CharField(max_length=200, blank=True)  # object path in the private bucket
    size_bytes = models.PositiveBigIntegerField(default=0)
    attempts = models.PositiveSmallIntegerField(default=0)
    requested_at = models.DateTimeField(auto_now_add=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["member", "status"]), models.Index(fields=["status", "expires_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["member"], condition=Q(status__in=["pending", "building"]), name="dataexport_one_open_per_member"
            )
        ]


class WorkEmailVerification(models.Model):
    """A pending proof that a member controls a work email. Only the domain and a code hash are stored, never the address."""

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="work_email_checks")
    email_domain = models.CharField(max_length=253)
    code_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["member"]), models.Index(fields=["expires_at"])]
