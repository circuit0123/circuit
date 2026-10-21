"""Permission helpers used by every endpoint. Deny by default: nothing here has a super_admin bypass.

Usage in a router:
    member = current_member(request)
    require_role(member, Role.FOUNDER)
    jobs = in_org(Job.objects.all(), member, "startup__claimed_by__organisation")
"""

from django.db.models import QuerySet

from core.errors import Forbidden


def require_role(member, *roles: str) -> None:
    if member.role not in roles:
        raise Forbidden()


def require_level(member, level: int) -> None:
    if member.verification_level < level:
        raise Forbidden(f"This needs verification level {level}")


def require_org_admin(member) -> int:
    """Partner admins act only inside their own organisation. Returns that organisation's id."""
    if member.role != "partner_admin" or member.organisation_id is None:
        raise Forbidden()
    return member.organisation_id


def in_org(queryset: QuerySet, member, field: str = "organisation") -> QuerySet:
    """Restrict a queryset to the member's own organisation. A member with no organisation sees nothing."""
    if member.organisation_id is None:
        return queryset.none()
    return queryset.filter(**{field: member.organisation_id})
