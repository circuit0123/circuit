"""Organisation rules. Routers stay thin; everything that decides lives here."""

import secrets

import structlog
from django.db import transaction

from apps.accounts.models import Member, Role
from apps.events.services import record
from apps.organisations.models import Organisation
from core.errors import ApiError, Conflict, Forbidden, NotFound

log = structlog.get_logger("organisations")

# No 0/O/1/I/L: join codes get read out loud and typed on phones.
JOIN_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
JOIN_CODE_LENGTH = 10

# A public mailbox says nothing about where someone studies or works.
PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "outlook.com", "hotmail.com", "live.com",
    "icloud.com", "me.com", "proton.me", "protonmail.com", "aol.com", "rediffmail.com", "zoho.com", "gmx.com",
    "mail.com", "yandex.com",
}  # fmt: skip

JOINABLE_ROLES = {Role.STUDENT, Role.FOUNDER, Role.MENTOR, Role.INVESTOR}


def generate_join_code() -> str:
    while True:
        code = "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))
        if not Organisation.objects.filter(join_code=code).exists():
            return code


def clean_domains(domains: list[str], exclude_org_id: int | None = None) -> list[str]:
    """Lowercase, de-duplicate, and reject public mail providers or a domain another organisation already owns.

    Domain-based auto-join trusts the first organisation that claims a domain, so each domain
    may belong to only one organisation.
    """
    cleaned: list[str] = []
    for raw in domains:
        d = raw.strip().lower().lstrip("@")
        if not d or "." not in d or " " in d or "@" in d:
            raise ValueError(f"'{raw}' is not a valid domain")
        if d in PUBLIC_EMAIL_DOMAINS:
            raise ValueError(f"'{d}' is a public mail provider and cannot identify an organisation")
        if d not in cleaned:
            cleaned.append(d)
    clash = Organisation.objects.filter(email_domains__overlap=cleaned)
    if exclude_org_id:
        clash = clash.exclude(pk=exclude_org_id)
    if cleaned and clash.exists():
        raise ValueError("Another organisation already uses one of these domains")
    return cleaned


def _ensure_joinable(member: Member) -> None:
    if member.role not in JOINABLE_ROLES:
        raise Forbidden()
    if member.organisation_id is not None:
        raise Conflict("You already belong to an organisation. Leave it first.", code="already_in_organisation")


def join_by_code(member: Member, code: str) -> Organisation:
    _ensure_joinable(member)
    org = Organisation.objects.filter(join_code=code.strip().upper()).first()
    if org is None:
        raise NotFound("That join code is not valid")
    _attach(member, org, "code")
    return org


def join_by_invite(member: Member, org: Organisation) -> bool:
    """Join the organisation an invite code carries. Quiet: someone who already has an organisation (or an admin role) stays
    where they are, and the code still gets them into the beta."""
    if member.organisation_id is not None or member.role not in JOINABLE_ROLES:
        return False
    _attach(member, org, "invite")
    return True


def _org_for_domain(domain: str) -> Organisation | None:
    """The one organisation that owns this domain. If two claim it (possible outside the admin form), nobody does."""
    if not domain:
        return None
    matches = list(Organisation.objects.filter(email_domains__contains=[domain])[:2])
    if len(matches) > 1:
        log.warning("org_domain_ambiguous", domain=domain)
        return None
    return matches[0] if matches else None


def join_by_email(member: Member, verified_email: str | None, quiet: bool = False) -> Organisation | None:
    """Join the organisation that owns the domain of an email the sign-in provider verified.

    `quiet` is for first login: no match is normal there, not an error.
    """
    domain = verified_email.rsplit("@", 1)[-1] if verified_email and "@" in verified_email else ""
    if quiet:
        if member.organisation_id is not None or member.role not in JOINABLE_ROLES:
            return None
        org = _org_for_domain(domain)
        if org is None:
            return None
    else:
        _ensure_joinable(member)
        org = _org_for_domain(domain)
        if org is None:
            raise ApiError(404, "no_matching_organisation", "No organisation uses your sign-in email's domain")
    _attach(member, org, "email_domain")
    return org


def _attach(member: Member, org: Organisation, method: str) -> None:
    member.organisation = org
    member.visible_to_org = False  # being visible to an organisation is consent given to that one; ask again
    member.save(update_fields=["organisation", "visible_to_org", "updated_at"])
    record("org.joined", actor=member, target_type="organisation", target_id=org.pk, method=method)


def leave(member: Member) -> None:
    if member.organisation_id is None:
        raise Conflict("You are not in an organisation", code="not_in_organisation")
    if member.role == Role.PARTNER_ADMIN:
        raise Forbidden("Partner admins cannot leave; ask a Circuit admin to reassign the organisation")
    org_id = member.organisation_id
    member.organisation = None
    member.visible_to_org = False
    member.save(update_fields=["organisation", "visible_to_org", "updated_at"])
    record("org.left", actor=member, target_type="organisation", target_id=org_id)


@transaction.atomic
def remove_member(admin: Member, member_id: int) -> None:
    """A partner admin removes someone from their own organisation. Anyone else's id is a plain 404."""
    if admin.role != Role.PARTNER_ADMIN or admin.organisation_id is None:
        raise Forbidden()  # also stops filter(organisation_id=None) from matching every org-less member
    target = Member.objects.select_for_update().filter(pk=member_id, organisation_id=admin.organisation_id).first()
    if target is None:
        raise NotFound()
    if target.pk == admin.pk or target.role == Role.PARTNER_ADMIN:
        raise Forbidden("Partner admins cannot be removed here")
    org_id = target.organisation_id
    target.organisation = None
    target.visible_to_org = False
    target.save(update_fields=["organisation", "visible_to_org", "updated_at"])
    record("org.member_removed", actor=admin, target_type="organisation", target_id=org_id, removed_member_id=target.pk)
