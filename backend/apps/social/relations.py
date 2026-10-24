"""Who is connected to, blocked by, or in the same organisation as whom. The one place the social rules are decided.

Minors (is_minor) are the reason this file exists: every social surface asks these functions instead of re-deriving
the rule. Where a rule says "not allowed", callers answer 404, so a stranger cannot learn that a minor exists.
"""

from django.db.models import Q, QuerySet

from apps.accounts.models import Connection, Member, Role
from apps.moderation.models import Block
from core.permissions import NETWORK_ROLES

SOCIAL_ROLES = NETWORK_ROLES  # who can post, react, follow, connect and read Pulse
MESSAGING_ROLES = (*NETWORK_ROLES, Role.PARTNER_ADMIN)  # org staff may message their own organisation (minors included)


def connected_ids(member_id: int) -> set[int]:
    pairs = Connection.objects.filter(Q(member_a_id=member_id) | Q(member_b_id=member_id)).values_list(
        "member_a_id", "member_b_id"
    )
    return {b if a == member_id else a for a, b in pairs}


def blocked_ids(member_id: int) -> set[int]:
    """People I blocked and people who blocked me. Either way, we stop seeing each other."""
    pairs = Block.objects.filter(Q(blocker_id=member_id) | Q(blocked_id=member_id)).values_list("blocker_id", "blocked_id")
    return {b if a == member_id else a for a, b in pairs}


def is_connected(a_id: int, b_id: int) -> bool:
    x, y = sorted((a_id, b_id))
    return Connection.objects.filter(member_a_id=x, member_b_id=y).exists()


def is_blocked(a_id: int, b_id: int) -> bool:
    return Block.objects.filter(Q(blocker_id=a_id, blocked_id=b_id) | Q(blocker_id=b_id, blocked_id=a_id)).exists()


def same_org(a: Member, b: Member) -> bool:
    return a.organisation_id is not None and a.organisation_id == b.organisation_id


def org_mate_ids(member: Member) -> set[int]:
    if member.organisation_id is None:
        return set()
    return set(
        Member.objects.filter(organisation_id=member.organisation_id, suspended_at__isnull=True, role__in=SOCIAL_ROLES)
        .exclude(pk=member.pk)
        .values_list("pk", flat=True)
    )


# -- posts ------------------------------------------------------------------------------------------------
def visible_posts(viewer: Member) -> QuerySet:
    """Posts the viewer may see, as one query. Mirrors can_see_post (the tests run both against the same cases)."""
    from apps.social.models import Post

    V = Post.Visibility
    conns = connected_ids(viewer.pk)
    rule = (
        Q(author=viewer)
        | Q(visibility=V.EVERYONE, author__is_minor=False, author__profile_visibility__in=["public", "members"])
        | Q(visibility__in=[V.EVERYONE, V.CONNECTIONS], author_id__in=conns)
    )
    if viewer.organisation_id is not None:
        rule |= Q(visibility=V.ORGANISATION, author__organisation_id=viewer.organisation_id)
    qs = Post.objects.filter(rule, author__suspended_at__isnull=True)
    own = Q(author=viewer)
    return qs.filter(own | Q(status=Post.Status.VISIBLE)).exclude(author_id__in=blocked_ids(viewer.pk))


def can_see_post(viewer: Member, post) -> bool:
    from apps.social.models import Post

    V = Post.Visibility
    author = post.author
    if author.pk == viewer.pk:
        return True
    if post.status != Post.Status.VISIBLE or author.suspended_at is not None or is_blocked(viewer.pk, author.pk):
        return False
    if post.visibility == V.ORGANISATION:
        return same_org(viewer, author)
    if is_connected(viewer.pk, author.pk):
        return True
    if post.visibility == V.EVERYONE:
        return not author.is_minor and author.profile_visibility != Member.Visibility.HIDDEN
    return False


# -- contact rules (messages, connection requests) ----------------------------------------------------------
def _open_to_strangers(recipient: Member) -> bool:
    """A stranger (not connected, not in the same organisation) may reach someone with a findable profile who allows requests."""
    return recipient.profile_visibility != Member.Visibility.HIDDEN and recipient.allow_requests


def may_message(sender: Member, recipient: Member) -> bool:
    """Under-18 rule for messages: a minor can only talk with their connections and with staff of their own organisation."""
    if sender.suspended_at or recipient.suspended_at or is_blocked(sender.pk, recipient.pk):
        return False
    if sender.role not in MESSAGING_ROLES or recipient.role not in MESSAGING_ROLES:
        return False
    if Role.PARTNER_ADMIN in (sender.role, recipient.role):
        return same_org(sender, recipient)  # org staff talk to their own organisation, nobody else
    connected = is_connected(sender.pk, recipient.pk)
    if sender.is_minor or recipient.is_minor:
        return connected
    return connected or same_org(sender, recipient) or _open_to_strangers(recipient)


def may_request_connection(sender: Member, recipient: Member) -> bool:
    """Connection requests need the same blocks/visibility, and a minor on either side means the same organisation."""
    if sender.role not in SOCIAL_ROLES or recipient.role not in SOCIAL_ROLES:
        return False
    if sender.suspended_at or recipient.suspended_at or is_blocked(sender.pk, recipient.pk):
        return False
    if sender.is_minor or recipient.is_minor:
        return same_org(sender, recipient)
    return same_org(sender, recipient) or _open_to_strangers(recipient)
