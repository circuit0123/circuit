from django.conf import settings
from django.db import models
from django.db.models import F, Q


class InviteCode(models.Model):
    """A way into the invite-only beta (F18). Single-use or capped multi-use, optional expiry, optional organisation."""

    class Kind(models.TextChoices):
        ADMIN = "admin"  # made by a super admin (Django admin or `manage.py invite_codes`)
        MEMBER = "member"  # one of the codes each beta member can hand out
        WAITLIST = "waitlist"  # emailed when a waitlist entry is approved

    code = models.CharField(max_length=16, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.ADMIN)
    max_uses = models.PositiveIntegerField(default=1)
    uses = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    organisation = models.ForeignKey(
        "organisations.Organisation", null=True, blank=True, on_delete=models.SET_NULL, related_name="invite_codes"
    )
    created_by = models.ForeignKey(  # the inviter, for member codes
        "accounts.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="invite_codes_created"
    )
    created_by_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.CharField(max_length=200, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(max_uses__gte=1), name="invitecode_max_uses_positive"),
            models.CheckConstraint(condition=Q(uses__lte=F("max_uses")), name="invitecode_uses_within_max"),
        ]
        indexes = [models.Index(fields=["created_by"]), models.Index(fields=["organisation"])]

    def __str__(self) -> str:
        return f"{self.code} ({self.kind}, {self.uses}/{self.max_uses})"


class BetaAccess(models.Model):
    """The member may use the app while BETA_MODE is on. Revoking keeps the row, so a code or the allowlist cannot quietly re-grant it."""

    class Source(models.TextChoices):
        CODE = "code"
        ALLOWLIST = "allowlist"
        APPROVED = "approved"  # a super admin approved a waitlist entry, or granted access by hand

    member = models.OneToOneField("accounts.Member", on_delete=models.CASCADE, related_name="beta")
    source = models.CharField(max_length=10, choices=Source.choices)
    invite_code = models.ForeignKey(InviteCode, null=True, blank=True, on_delete=models.SET_NULL, related_name="redemptions")
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        indexes = [models.Index(fields=["invite_code"])]

    def __str__(self) -> str:
        return f"Beta access for member {self.member_id} ({self.source})"


class WaitlistEntry(models.Model):
    """Someone who asked for an invite on the landing site. No account needed; the email is the only identifier."""

    class Role(models.TextChoices):
        STUDENT = "student"
        FOUNDER = "founder"
        MENTOR = "mentor"
        INVESTOR = "investor"
        PARTNER = "partner"

    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"

    email = models.CharField(max_length=254, unique=True)  # lower-cased plain ASCII (core.codes.plain_email)
    role = models.CharField(max_length=10, choices=Role.choices)
    city = models.CharField(max_length=100, blank=True)
    college = models.CharField(max_length=200, blank=True)
    note = models.CharField(max_length=500, blank=True)
    src = models.CharField(max_length=40, blank=True)  # which landing page it came from
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    invite_code = models.ForeignKey(InviteCode, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "-created_at"])]

    def __str__(self) -> str:
        return f"Waitlist #{self.pk} ({self.role}, {self.status})"  # never the address: str() ends up in logs and admin messages


class AllowlistEntry(models.Model):
    """An email that gets in without a code. Matched against the Supabase-verified sign-in email only."""

    email = models.CharField(max_length=254, unique=True)  # lower-cased plain ASCII
    note = models.CharField(max_length=200, blank=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Allowlist #{self.pk}"


class JoinVisit(models.Model):
    """How many times a landing link with this `src` was opened on this day. A count only: no member, address or browser is stored."""

    src = models.CharField(max_length=40, blank=True)
    day = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["src", "day"], name="join_visit_src_day_unique")]

    def __str__(self) -> str:
        return f"{self.src or '(none)'} {self.day}: {self.count}"
