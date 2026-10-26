"""Invite-only beta (F18): who gets in, and how. Routers stay thin; the rules live here."""

import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import structlog
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import Member, Role
from apps.beta.models import AllowlistEntry, BetaAccess, InviteCode, JoinVisit, WaitlistEntry
from apps.events.services import record
from apps.moderation.models import AuditLog
from core import ist
from core.codes import ALPHABET, plain_email
from core.email import queue_email
from core.errors import ApiError

log = structlog.get_logger("beta")

CODE_LENGTH = 10  # 31 symbols ** 10 is about 49 bits: not guessable, and short enough to read out or type on a phone
_CODE_SHAPE = re.compile(rf"[{ALPHABET}]{{{CODE_LENGTH}}}")
ADMIN_ROLES = {Role.PARTNER_ADMIN, Role.SUPER_ADMIN}  # appointed by a super admin, so never gated


class InvalidCode(ApiError):
    """The one answer for an unknown, expired, used-up or revoked code (and for a revoked member): nothing here helps guessing."""

    def __init__(self):
        super().__init__(400, "invalid_code", "That code doesn't work. Check it and try again.")


# -- codes -------------------------------------------------------------------------------------


def generate_code() -> str:
    """A fresh random code from the system CSPRNG. The unique constraint is the final word on collisions."""
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        if not InviteCode.objects.filter(code=code).exists():
            return code


def normalise_code(raw: str) -> str | None:
    """What a person typed or pasted -> canonical code, or None if it cannot be one (so no database lookup happens)."""
    code = re.sub(r"[\s-]", "", raw).upper()
    return code if _CODE_SHAPE.fullmatch(code) else None


def invite_link(code: str, src: str = "invite") -> str:
    return f"{settings.APP_URL.rstrip('/')}/join?{urlencode({'code': code, 'src': src})}"


def create_code(
    *,
    kind: str = InviteCode.Kind.ADMIN,
    max_uses: int = 1,
    days: int | None = None,
    organisation=None,
    created_by=None,
    staff=None,
    note="",
) -> InviteCode:
    for _ in range(5):
        try:
            with transaction.atomic():
                return InviteCode.objects.create(
                    code=generate_code(),
                    kind=kind,
                    max_uses=max_uses,
                    expires_at=timezone.now() + timedelta(days=days) if days else None,
                    organisation=organisation,
                    created_by=created_by,
                    created_by_staff=staff,
                    note=note[:200],
                )
        except IntegrityError:  # two requests drew the same code in the same instant
            continue
    raise RuntimeError("could not generate a unique invite code")


def code_status(code: InviteCode) -> str:
    if code.revoked_at is not None:
        return "revoked"
    if code.uses >= code.max_uses:
        return "used"
    if code.expires_at is not None and code.expires_at <= timezone.now():
        return "expired"
    return "available"


# -- who may pass the gate -------------------------------------------------------------------------


def _grant(member: Member, source: str, invite_code: InviteCode | None = None) -> BetaAccess | None:
    """Create the member's access row. Returns None if another request created it first."""
    try:
        with transaction.atomic():
            access = BetaAccess.objects.create(member=member, source=source, invite_code=invite_code)
    except IntegrityError:
        return None
    record(
        "beta.access_granted",
        actor=member,
        target_type="member",
        target_id=member.pk,
        source=source,
        inviter_id=invite_code.created_by_id if invite_code else None,
    )
    return access


def has_access(member: Member, verified_email: str | None) -> bool:
    """May this member use the app while BETA_MODE is on?

    Order: an access row decides (revoked means no, whatever else is true); admins pass; otherwise the Supabase-verified
    sign-in email (never an address the client sent) can be on the allowlist or on an approved waitlist entry, which grants.
    """
    access = BetaAccess.objects.filter(member=member).first()
    if access is not None:
        return access.revoked_at is None
    if member.role in ADMIN_ROLES:
        return True
    email = plain_email(verified_email) if verified_email else None
    if email:
        if AllowlistEntry.objects.filter(email=email).exists():
            _grant(member, BetaAccess.Source.ALLOWLIST)
            return True
        if WaitlistEntry.objects.filter(email=email, status=WaitlistEntry.Status.APPROVED).exists():
            _grant(member, BetaAccess.Source.APPROVED)
            return True
    return False


def redeem(member: Member, raw_code: str) -> dict:
    """Use an invite code. Everything that can go wrong with the code gives the same InvalidCode answer.

    The member row is locked first, then the code row, always in that order. The code lock is what makes two people racing
    for the last use come out as exactly one success: the second waits, then sees the code is used up.
    """
    code = normalise_code(raw_code)
    with transaction.atomic():
        locked = Member.objects.select_for_update().get(pk=member.pk)
        access = BetaAccess.objects.filter(member=locked).first()
        if access is not None:
            if access.revoked_at is not None:
                raise InvalidCode()
            # Already in (a double tap, or a second invite link): say so without using up anyone's code.
            return {"beta_access": True, "organisation_id": locked.organisation_id}
        invite = InviteCode.objects.select_for_update().filter(code=code).first() if code else None
        if invite is None or code_status(invite) != "available":
            raise InvalidCode()
        invite.uses += 1
        invite.save(update_fields=["uses"])
        _grant(locked, BetaAccess.Source.CODE, invite)
        if invite.organisation is not None and locked.organisation_id is None:
            from apps.organisations.services import join_by_invite

            join_by_invite(locked, invite.organisation)
        organisation_id = locked.organisation_id
    return {"beta_access": True, "organisation_id": organisation_id}


def revoke_access(member: Member, staff) -> bool:
    access = BetaAccess.objects.filter(member=member, revoked_at__isnull=True).first()
    if access is None:
        return False
    access.revoked_at, access.revoked_by = timezone.now(), staff
    access.save(update_fields=["revoked_at", "revoked_by"])
    return True


def restore_access(member: Member) -> bool:
    return bool(BetaAccess.objects.filter(member=member, revoked_at__isnull=False).update(revoked_at=None, revoked_by=None))


def revoke_code(code: InviteCode) -> bool:
    if code.revoked_at is not None:
        return False
    code.revoked_at = timezone.now()
    code.save(update_fields=["revoked_at"])
    return True


# -- member invites (3 each) ----------------------------------------------------------------------


def member_invites(member: Member) -> list[dict]:
    """The member's own invite codes, creating the missing ones up to INVITES_PER_MEMBER.

    Counts every code ever made for the member, revoked ones included, so a revoked code is not replaced for free. The
    member row is locked so two parallel calls cannot both top up.
    """
    with transaction.atomic():
        Member.objects.select_for_update().get(pk=member.pk)
        existing = InviteCode.objects.filter(created_by=member, kind=InviteCode.Kind.MEMBER)
        for _ in range(max(0, settings.INVITES_PER_MEMBER - existing.count())):
            code = create_code(kind=InviteCode.Kind.MEMBER, created_by=member, note="member invite")
            record("invite.created", actor=member, target_type="invite_code", target_id=code.pk)
        rows = list(InviteCode.objects.filter(created_by=member, kind=InviteCode.Kind.MEMBER).order_by("id"))
    return [{"code": c.code, "link": invite_link(c.code), "status": code_status(c)} for c in rows]


# -- waitlist ----------------------------------------------------------------------------------


def join_waitlist(*, email: str, role: str, city: str, college: str, note: str, src: str) -> None:
    """Add an email to the waitlist. Returns nothing either way: a repeat looks exactly like a first sign-up."""
    clean = plain_email(email.strip())
    if clean is None:
        raise ApiError(422, "validation_error", "Enter a valid email address", {"field": "email"})
    _, created = WaitlistEntry.objects.get_or_create(
        email=clean, defaults={"role": role, "city": city.strip(), "college": college.strip(), "note": note.strip(), "src": src}
    )
    if created:
        record("waitlist.joined", role=role, src=src)


def approve_waitlist(entry: WaitlistEntry, staff) -> InviteCode | None:
    """Let a waitlist entry in: sign-in with that verified email now passes the gate, and a one-tap invite email goes out.

    Returns None if the entry was already approved (so a second click sends nothing).
    """
    with transaction.atomic():
        entry = WaitlistEntry.objects.select_for_update().get(pk=entry.pk)
        if entry.status == WaitlistEntry.Status.APPROVED:
            return None
        code = create_code(
            kind=InviteCode.Kind.WAITLIST, days=settings.INVITE_EXPIRY_DAYS_WAITLIST, staff=staff, note=f"waitlist #{entry.pk}"
        )
        entry.status, entry.reviewed_by, entry.reviewed_at, entry.invite_code = (
            WaitlistEntry.Status.APPROVED,
            staff,
            timezone.now(),
            code,
        )
        entry.save(update_fields=["status", "reviewed_by", "reviewed_at", "invite_code"])
        queue_email(
            entry.email,
            "waitlist_invite",
            "You're in. Your Circuit invite",
            "Good news: you're off the Circuit waitlist.\n\n"
            f"Tap to get started:\n{invite_link(code.code)}\n\n"
            f"The link works once and expires in {settings.INVITE_EXPIRY_DAYS_WAITLIST} days.\n\n"
            "Circuit matches people on what they need and what they can offer. See you inside.\n",
        )
        AuditLog.objects.create(
            actor=staff,
            action="waitlist.approve",
            target_type="beta.waitlistentry",
            target_id=str(entry.pk),
            payload={"invite_code_id": code.pk},
        )
    return code


def reject_waitlist(entry: WaitlistEntry, staff) -> bool:
    if entry.status == WaitlistEntry.Status.REJECTED:
        return False
    entry.status, entry.reviewed_by, entry.reviewed_at = WaitlistEntry.Status.REJECTED, staff, timezone.now()
    entry.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    AuditLog.objects.create(actor=staff, action="waitlist.reject", target_type="beta.waitlistentry", target_id=str(entry.pk))
    return True


def count_visit(src: str) -> None:
    """Add one to today's (India time) count for this source. Atomic, so concurrent visits are not lost."""
    day = ist.day()
    updated = JoinVisit.objects.filter(src=src, day=day).update(count=F("count") + 1)
    if not updated:
        JoinVisit.objects.bulk_create([JoinVisit(src=src, day=day, count=0)], ignore_conflicts=True)
        JoinVisit.objects.filter(src=src, day=day).update(count=F("count") + 1)
